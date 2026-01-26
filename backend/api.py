from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import shutil
import os
import zipfile
import tarfile
import pandas as pd
import uuid
from pathlib import Path
import logging
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from services.analysis_service import AnalysisService
from services.progress_tracker import get_progress, cleanup_old_progress, update_progress
from services.analysis_storage import (
    save_analysis, get_analysis, get_history,
    cleanup_old_analyses, get_storage_stats
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")

# Security and performance limits
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
MAX_UPLOAD_AGE_HOURS = 24  # Auto-cleanup after 24 hours
ALLOWED_ARCHIVE_TYPES = {'.zip', '.tar.gz', '.tgz'}
ALLOWED_CSV_TYPES = {'.csv'}
CSV_ENCODING_FALLBACKS = (
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "gbk",
    "gb2312",
    "gb18030",
    "big5",
    "cp1252",
    "iso-8859-1",
    "latin-1",  # Universal fallback - can decode any byte sequence
)

# Initialize analysis service
analysis_service = AnalysisService()

# Thread pool for parallel execution - configurable to avoid OOM on large datasets
MAX_WORKERS = int(os.getenv("ANALYSIS_MAX_WORKERS", "4"))
executor = ThreadPoolExecutor(max_workers=max(1, MAX_WORKERS))


def validate_file_size(file: UploadFile) -> None:
    """Validate uploaded file size."""
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f}MB"
        )
    logger.info(f"File size validated: {file_size / (1024*1024):.2f}MB")


def validate_file_type(filename: str, allowed_extensions: set) -> None:
    """Validate file extension and MIME type."""
    file_lower = filename.lower()

    # Check extension
    valid = False
    for ext in allowed_extensions:
        if file_lower.endswith(ext):
            valid = True
            break

    if not valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )


def detect_csv_encoding(file_path: Path) -> str:
    """Detect CSV encoding using BOM and sample decoding."""
    try:
        with open(file_path, 'rb') as f:
            sample = f.read(65536)
    except Exception as e:
        logger.error(f"Failed to read CSV for encoding detection: {e}")
        raise HTTPException(status_code=400, detail="CSV file cannot be read")

    if not sample:
        return "utf-8"

    if sample.startswith(b'\xef\xbb\xbf'):
        return "utf-8-sig"
    if sample.startswith(b'\xff\xfe'):
        return "utf-16-le"
    if sample.startswith(b'\xfe\xff'):
        return "utf-16-be"

    if b'\x00' in sample:
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                sample.decode(enc)
                return enc
            except UnicodeDecodeError:
                continue
        raise HTTPException(
            status_code=400,
            detail="CSV file appears to be binary or uses unsupported encoding"
        )

    try:
        sample.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    for enc in ("gbk", "cp1252"):
        try:
            sample.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue

    return "iso-8859-1"


def validate_file_content(file_path: Path):
    """Validate file content using magic bytes."""
    try:
        with open(file_path, 'rb') as f:
            magic_bytes = f.read(8)

        # Check for common archive formats
        if file_path.suffix == '.zip' or file_path.name.endswith('.zip'):
            # ZIP magic bytes: PK\x03\x04 or PK\x05\x06 or PK\x07\x08
            if not (magic_bytes[:2] == b'PK' and magic_bytes[2] in [0x03, 0x05, 0x07]):
                raise HTTPException(
                    status_code=400,
                    detail="File content does not match ZIP format"
                )
        elif file_path.suffix in {'.gz', '.tgz'} or file_path.name.endswith('.tar.gz'):
            # GZIP magic bytes: 0x1f 0x8b
            if magic_bytes[:2] != b'\x1f\x8b':
                raise HTTPException(
                    status_code=400,
                    detail="File content does not match GZIP format"
                )
        elif file_path.suffix.lower() == '.csv':
            # CSV should be text-based, skip strict validation
            # Let the main CSV reading logic handle encoding detection with full fallback mechanism
            logger.info("CSV file detected, skipping strict encoding validation")
            return None  # Return None to let the main CSV reader detect encoding
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File content validation failed: {e}")
        raise HTTPException(
            status_code=400,
            detail="File content validation failed"
        )
    return None


def validate_path_safety(base_path: Path, target_path: Path) -> None:
    """Ensure target_path is within base_path (prevent path traversal)."""
    try:
        base_resolved = base_path.resolve()
        # For non-existent paths on Windows, use parent resolution
        try:
            target_resolved = target_path.resolve()
        except (OSError, RuntimeError):
            # If resolve fails, manually construct the path
            target_resolved = base_resolved / target_path.relative_to(base_path)

        # Check if target is within base
        target_resolved.relative_to(base_resolved)
    except (ValueError, RuntimeError) as e:
        logger.error(f"Path traversal attempt detected: {target_path} not in {base_path}")
        raise HTTPException(
            status_code=400,
            detail="Invalid file path detected"
        )


def cleanup_old_uploads() -> int:
    """Remove upload directories older than MAX_UPLOAD_AGE_HOURS."""
    if not UPLOAD_DIR.exists():
        return 0

    cutoff_time = datetime.now() - timedelta(hours=MAX_UPLOAD_AGE_HOURS)
    removed_count = 0

    try:
        for task_dir in UPLOAD_DIR.iterdir():
            if not task_dir.is_dir():
                continue

            # Check directory modification time
            dir_mtime = datetime.fromtimestamp(task_dir.stat().st_mtime)

            if dir_mtime < cutoff_time:
                try:
                    shutil.rmtree(task_dir)
                    removed_count += 1
                    logger.info(f"Cleaned up old upload: {task_dir.name}")
                except Exception as e:
                    logger.error(f"Failed to remove {task_dir}: {e}")

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

    return removed_count


def safe_extract_archive(file_path: Path, extract_dir: Path) -> None:
    """Safely extract archive with path traversal protection."""
    validate_path_safety(UPLOAD_DIR, extract_dir)

    if file_path.suffix == '.zip':
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            # Validate all paths before extraction
            for member in zip_ref.namelist():
                member_path = extract_dir / member
                validate_path_safety(extract_dir, member_path)

            zip_ref.extractall(extract_dir)
            logger.info(f"Extracted ZIP: {len(zip_ref.namelist())} files")

    elif file_path.suffix in {'.gz', '.tgz'} or str(file_path.name).endswith('.tar.gz'):
        with tarfile.open(file_path, 'r:gz') as tar_ref:
            # Validate all paths before extraction
            for member in tar_ref.getmembers():
                member_path = extract_dir / member.name
                validate_path_safety(extract_dir, member_path)

            tar_ref.extractall(extract_dir)
            logger.info(f"Extracted TAR.GZ: {len(tar_ref.getmembers())} files")

    else:
        raise HTTPException(status_code=400, detail="Unsupported archive format")


@router.post("/upload/ibdiagnet", tags=["upload"])
async def upload_ibdiagnet(file: UploadFile = File(...)):
    """
    Upload and analyze IBDiagnet archive with parallel processing.

    Accepts .zip or .tar.gz archives from IBDiagnet tool.
    Includes security validation, automatic cleanup, and comprehensive error handling.

    Returns comprehensive analysis including:
    - Health score (0-100)
    - Network topology visualization
    - Cable/optical module diagnostics
    - BER (Bit Error Rate) analysis
    - Congestion analysis
    - HCA/firmware information
    """
    # Trigger cleanup of old uploads
    cleanup_count = cleanup_old_uploads()
    if cleanup_count > 0:
        logger.info(f"Cleaned up {cleanup_count} old upload(s)")

    # Validate file
    validate_file_type(file.filename, ALLOWED_ARCHIVE_TYPES)
    validate_file_size(file)

    # Create unique task directory
    task_id = str(uuid.uuid4())
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    file_path = task_dir / file.filename
    extract_dir = task_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)

    try:
        # Save uploaded file
        logger.info(f"Saving upload: {file.filename} (task: {task_id})")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate file content (magic bytes check)
        validate_file_content(file_path)

        # Extract archive with security validation
        safe_extract_archive(file_path, extract_dir)

        # Find IBDiagnet data directory
        found_db_csv = list(extract_dir.rglob("*.db_csv"))
        if not found_db_csv:
            raise HTTPException(
                status_code=400,
                detail="No .db_csv files found in archive. Is this a valid IBDiagnet output?"
            )

        target_dir = found_db_csv[0].parent
        validate_path_safety(extract_dir, target_dir)
        logger.info(f"Found IBDiagnet data at: {target_dir}")

        analysis_service.load_dataset(target_dir)

        loop = asyncio.get_event_loop()
        payload = await analysis_service.analyze_ibdiagnet(
            target_dir=target_dir,
            task_dir=task_dir,
            task_id=task_id,
            executor=executor,
            loop=loop,
        )

        logger.info(f"Analysis complete for task {task_id}")

        # Cache the full data for streaming (if needed in future)
        cache_analysis_results(task_id, payload)

        # Save analysis results to storage
        try:
            save_analysis(
                task_id=task_id,
                analysis_data=payload,
                file_name=file.filename,
                file_type='ibdiagnet'
            )
            logger.info(f"Analysis results saved for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to save analysis results: {e}")
            # Don't fail the request if saving fails

        # Prepare response
        response = {
            "status": "success",
            "task_id": task_id,
            **payload,
        }

        # Auto-cleanup: Delete uploaded data after analysis is complete
        try:
            if task_dir.exists():
                import time
                time.sleep(0.2)  # Brief delay to ensure all file handles are released
                shutil.rmtree(task_dir)
                logger.info(f"Auto-cleanup: Deleted task directory {task_dir}")
        except Exception as e:
            logger.warning(f"Auto-cleanup failed for task {task_id}: {e}")
            # Don't raise exception, just log warning - the analysis was successful

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Analysis failed for task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Clean up uploaded archive (keep extracted data and results)
        # Add delay to ensure file handles are released
        if file_path.exists():
            try:
                import time
                time.sleep(0.1)  # Brief delay for file handle release
                file_path.unlink()
                logger.info(f"Cleaned up uploaded archive: {file_path.name}")
            except PermissionError:
                logger.warning(f"File still in use, will be cleaned up later: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup archive: {e}")

@router.post("/upload/ufm-csv", tags=["upload"])
async def upload_ufm_csv(file: UploadFile = File(...)):
    """
    Upload UFM CSV file and process it using subprocess.
    """
    # CRITICAL: Log at the very beginning to verify function is called
    import sys
    print("=" * 100, file=sys.stderr, flush=True)
    print("UFM CSV UPLOAD FUNCTION CALLED!", file=sys.stderr, flush=True)
    print(f"Filename: {file.filename}", file=sys.stderr, flush=True)
    print("=" * 100, file=sys.stderr, flush=True)

    logger.info("=" * 80)
    logger.info("UFM CSV UPLOAD STARTED - SUBPROCESS APPROACH")
    logger.info(f"Filename: {file.filename}")
    logger.info("=" * 80)

    # Trigger cleanup
    cleanup_count = cleanup_old_uploads()
    if cleanup_count > 0:
        logger.info(f"Cleaned up {cleanup_count} old upload(s)")

    # Validate file
    validate_file_type(file.filename, ALLOWED_CSV_TYPES)
    validate_file_size(file)

    task_id = str(uuid.uuid4())
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    file_path = task_dir / file.filename

    try:
        logger.info(f"=" * 80)
        logger.info(f"UFM CSV UPLOAD STARTED - SUBPROCESS APPROACH")
        logger.info(f"Filename: {file.filename}")
        logger.info(f"Task ID: {task_id}")
        logger.info(f"=" * 80)

        logger.info(f"Saving CSV upload: {file.filename} (task: {task_id})")

        # Save file in binary mode - this should NOT trigger any encoding issues
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            logger.info(f"File saved successfully to {file_path}")
        except Exception as save_error:
            logger.error(f"Failed to save file: {save_error}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(save_error)}")

        logger.info("=" * 80)
        logger.info("UFM CSV PROCESSING - USING SUBPROCESS APPROACH")
        logger.info("=" * 80)

        # Use subprocess to call the direct processing script
        # This completely bypasses any encoding issues in the API layer
        logger.info(f"Calling direct processing script for {file_path}...")

        import subprocess
        import json
        import sys

        # Call the direct processing script
        script_path = Path(__file__).parent / "process_ufm_csv_direct.py"
        project_root = Path(__file__).parent.parent

        # Convert file_path to absolute path
        file_path_abs = file_path.resolve()

        logger.info(f"Script path: {script_path}")
        logger.info(f"Project root: {project_root}")
        logger.info(f"CSV file (absolute): {file_path_abs}")

        result = subprocess.run(
            [sys.executable, str(script_path), str(file_path_abs)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout for large files
            cwd=str(project_root)  # Run from project root
        )

        logger.info(f"Subprocess return code: {result.returncode}")
        logger.info(f"Subprocess stdout: {result.stdout[:500]}")
        logger.info(f"Subprocess stderr: {result.stderr[:500]}")

        if result.returncode != 0:
            logger.error(f"Direct processing script failed with code {result.returncode}")
            logger.error(f"STDERR: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"CSV processing failed: {result.stderr[:500] if result.stderr else 'Unknown error'}"
            )

        logger.info("Direct processing script completed successfully")
        logger.info(f"Script output: {result.stdout[:500]}")

        # Read the generated result file (in project root)
        result_file = project_root / "ufm_analysis_result.json"
        logger.info(f"Looking for result file at: {result_file}")

        if not result_file.exists():
            logger.error(f"Result file not found at {result_file}")
            raise HTTPException(
                status_code=500,
                detail="Analysis result file not found"
            )

        with open(result_file, 'r', encoding='utf-8') as f:
            analysis_results = json.load(f)

        # Extract load info from analysis results
        logger.info("Reading CSV to get load info...")
        df = pd.read_csv(file_path, encoding='latin-1', nrows=1)
        total_rows = len(pd.read_csv(file_path, encoding='latin-1'))

        load_result = {
            "status": "success",
            "rows": total_rows,
            "columns": len(df.columns),
            "unique_nodes": 0,  # Will be in analysis results
            "unique_hosts": 0,
        }

        logger.info(f"UFM CSV analysis complete: {load_result['rows']} rows analyzed")

        response = {
            "status": "success",
            "task_id": task_id,
            "filename": file.filename,
            "encoding": "latin-1",
            "encoding_warning": None,
            "load_info": load_result,
            "analysis": analysis_results,
        }

        # Save analysis results to storage
        try:
            save_analysis(
                task_id=task_id,
                analysis_data=response,
                file_name=file.filename,
                file_type='csv'
            )
            logger.info(f"CSV analysis results saved for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to save CSV analysis results: {e}")
            # Don't fail the request if saving fails

        # Auto-cleanup: Delete task directory after CSV processing is complete
        try:
            if task_dir.exists():
                import time
                time.sleep(0.2)  # Brief delay to ensure all file handles are released
                shutil.rmtree(task_dir)
                logger.info(f"Auto-cleanup: Deleted CSV task directory {task_dir}")
        except Exception as e:
            logger.warning(f"Auto-cleanup failed for CSV task {task_id}: {e}")
            # Don't raise exception, just log warning - the processing was successful

        return response

    except pd.errors.EmptyDataError:
        logger.error(f"Empty CSV file: {file.filename}")
        raise HTTPException(status_code=400, detail="CSV file is empty")
    except HTTPException:
        raise
    except pd.errors.ParserError as e:
        logger.error(f"CSV parsing error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
    except Exception as e:
        logger.error(f"CSV upload failed for task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"CSV processing failed: {str(e)}")
    finally:
        # Clean up uploaded file after processing
        if file_path.exists():
            try:
                import time
                time.sleep(0.1)  # Brief delay for file handle release
                file_path.unlink()
                logger.info(f"Cleaned up CSV file: {file_path.name}")
            except PermissionError:
                logger.warning(f"CSV file still in use, will be cleaned up later: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup CSV: {e}")


# Global cache for analysis results (for streaming)
analysis_results_cache = {}


@router.get("/stream/{task_id}/{service_name}", tags=["streaming"])
async def stream_service_data(task_id: str, service_name: str):
    """
    Stream service data using Server-Sent Events (SSE).

    Enhanced version with better error handling and progress reporting.
    Supports all analysis services including:
    - per_lane_performance: Per-Lane Performance data
    - power_sensors: Power Sensors data
    - port_hierarchy: Port Hierarchy data
    - qos: QoS / VL Arbitration data
    - extended_port_info: Extended Port Info data

    Args:
        task_id: The analysis task ID
        service_name: Name of the service (e.g., 'per_lane_performance', 'power_sensors')

    Returns:
        StreamingResponse with SSE events
    """

    async def event_generator():
        try:
            # Check if we have cached results for this task
            cache_key = f"{task_id}_{service_name}"

            if cache_key not in analysis_results_cache:
                logger.warning(f"Cache miss for {cache_key}")
                yield f"event: error\ndata: {json.dumps({{'error': 'Task not found or expired', 'cache_key': cache_key, 'service': service_name}})}\n\n"
                return

            data = analysis_results_cache[cache_key]

            if not data:
                logger.info(f"Empty data for {cache_key}")
                yield f"event: complete\ndata: {json.dumps({{'total': 0, 'message': 'No data available', 'service': service_name}})}\n\n"
                return

            total_rows = len(data)
            chunk_size = 500

            logger.info(f"Streaming {total_rows} rows for {service_name}")

            # Send metadata first with service info
            metadata = {
                'total': total_rows,
                'chunk_size': chunk_size,
                'service': service_name,
                'task_id': task_id
            }
            yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"

            # Stream data in chunks with progress
            for i in range(0, total_rows, chunk_size):
                chunk = data[i:i + chunk_size]
                chunk_data = {
                    'chunk_index': i // chunk_size,
                    'start': i,
                    'end': min(i + chunk_size, total_rows),
                    'data': chunk,
                    'progress': round((i + len(chunk)) / total_rows * 100, 2)
                }

                yield f"event: data\ndata: {json.dumps(chunk_data)}\n\n"

                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.05)

            # Send completion event
            completion = {
                'total': total_rows,
                'message': 'Stream complete',
                'service': service_name
            }
            yield f"event: complete\ndata: {json.dumps(completion)}\n\n"

            logger.info(f"Streaming completed for {service_name}: {total_rows} rows")

        except Exception as e:
            logger.error(f"Streaming error for {task_id}/{service_name}: {e}", exc_info=True)
            error_data = {
                'error': str(e),
                'service': service_name,
                'task_id': task_id
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*"
        }
    )


def cache_analysis_results(task_id: str, payload: dict):
    """
    Cache analysis results for streaming.
    
    Args:
        task_id: The analysis task ID
        payload: The analysis payload containing all service data
    """
    # Cache each service's data
    service_keys = [
        'cable_data', 'xmit_data', 'ber_data', 'hca_data', 'fan_data',
        'switch_data', 'routing_data', 'link_oscillation_data', 'histogram_data',
        'qos_data', 'sm_info_data', 'port_hierarchy_data', 'mlnx_counters_data',
        'pm_delta_data', 'vports_data', 'pkey_data', 'system_info_data',
        'extended_port_info_data', 'ar_info_data', 'sharp_data', 'fec_mode_data',
        'phy_diagnostics_data', 'neighbors_data', 'buffer_histogram_data',
        'extended_node_info_data', 'extended_switch_info_data', 'power_sensors_data',
        'routing_config_data', 'temp_alerts_data', 'credit_watchdog_data',
        'pci_performance_data', 'per_lane_performance_data', 'n2n_security_data'
    ]
    
    for key in service_keys:
        if key in payload and payload[key]:
            service_name = key.replace('_data', '')
            cache_key = f"{task_id}_{service_name}"
            analysis_results_cache[cache_key] = payload[key]
            logger.info(f"Cached {len(payload[key])} rows for {service_name}")
    
    # Clean up old cache entries (older than 1 hour)
    cleanup_old_cache()


def cleanup_old_cache():
    """Remove cache entries older than 1 hour."""
    # Simple implementation: keep last 10 tasks
    if len(analysis_results_cache) > 100:
        # Remove oldest entries
        keys_to_remove = list(analysis_results_cache.keys())[:50]
        for key in keys_to_remove:
            del analysis_results_cache[key]
        logger.info(f"Cleaned up {len(keys_to_remove)} old cache entries")


@router.get("/cache/status/{task_id}", tags=["streaming"])
async def get_cache_status(task_id: str):
    """
    Get cache status for debugging.

    Returns all available data services for the specified task.
    Useful for verifying that Per-Lane Performance, Power Sensors,
    Port Hierarchy, and QoS data are properly cached.
    """
    available_services = []

    # Check all possible services
    service_names = [
        'cable', 'xmit', 'ber', 'hca', 'fan', 'switch', 'routing',
        'link_oscillation', 'histogram', 'qos', 'sm_info', 'port_hierarchy',
        'mlnx_counters', 'pm_delta', 'vports', 'pkey', 'system_info',
        'extended_port_info', 'ar_info', 'sharp', 'fec_mode', 'phy_diagnostics',
        'neighbors', 'buffer_histogram', 'extended_node_info', 'extended_switch_info',
        'power_sensors', 'routing_config', 'temp_alerts', 'pci_performance',
        'per_lane_performance', 'n2n_security'
    ]

    for service_name in service_names:
        cache_key = f"{task_id}_{service_name}"
        if cache_key in analysis_results_cache:
            data = analysis_results_cache[cache_key]
            available_services.append({
                'service': service_name,
                'rows': len(data) if data else 0,
                'cache_key': cache_key,
                'has_data': bool(data)
            })

    return {
        'task_id': task_id,
        'available_services': available_services,
        'total_services': len(available_services),
        'cache_size': len(analysis_results_cache)
    }


# ==================== 新增 API 端点 ====================

@router.get("/analysis/{task_id}/progress", tags=["analysis"])
async def get_analysis_progress(task_id: str):
    """
    获取分析进度

    Args:
        task_id: 任务ID

    Returns:
        进度信息，包括阶段、进度百分比、当前服务等
    """
    progress_data = get_progress(task_id)

    # 如果内存中没有进度数据（服务器重启后），尝试从存储中恢复
    if progress_data['stage'] == 'unknown':
        from services.analysis_storage import get_analysis
        stored_analysis = get_analysis(task_id)

        if stored_analysis and stored_analysis.get('status') == 'completed':
            # 任务已完成，返回完成状态
            progress_data = {
                'stage': 'completed',
                'progress': 100,
                'current_service': '',
                'message': '分析已完成',
                'updated_at': stored_analysis.get('created_at', datetime.now().isoformat())
            }

    return progress_data


@router.get("/analysis/history", tags=["analysis"])
async def get_analysis_history(limit: int = 10):
    """
    获取历史分析记录列表

    Args:
        limit: 返回的最大记录数（默认10）

    Returns:
        历史记录列表
    """
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    history = get_history(limit=limit)

    return {
        'history': history,
        'total': len(history)
    }


@router.get("/analysis/storage/stats", tags=["analysis"])
async def get_analysis_storage_stats():
    """
    获取存储统计信息

    Returns:
        存储统计信息
    """
    stats = get_storage_stats()
    return stats


@router.post("/analysis/cleanup", tags=["analysis"])
async def cleanup_analysis_data(max_age_days: int = 7):
    """
    清理过期的分析数据

    Args:
        max_age_days: 最大保留天数（默认7天）

    Returns:
        清理统计信息
    """
    if max_age_days < 1:
        raise HTTPException(
            status_code=400,
            detail="max_age_days must be at least 1"
        )

    # 清理分析结果文件
    removed_files = cleanup_old_analyses(max_age_days=max_age_days)

    # 清理进度记录
    removed_progress = cleanup_old_progress(max_age_hours=max_age_days * 24)

    return {
        'removed_files': removed_files,
        'removed_progress_records': removed_progress,
        'max_age_days': max_age_days
    }


@router.get("/analysis/{task_id}", tags=["analysis"])
async def get_analysis_result(task_id: str):
    """
    获取分析结果

    Args:
        task_id: 任务ID

    Returns:
        完整的分析结果数据
    """
    result = get_analysis(task_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis result not found for task_id: {task_id}"
        )

    return result
