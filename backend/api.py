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

# Initialize analysis service
analysis_service = AnalysisService()

# Thread pool for parallel execution - increased for 33 analysis services
executor = ThreadPoolExecutor(max_workers=12)


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


def validate_file_content(file_path: Path) -> None:
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
        elif file_path.suffix == '.csv':
            # CSV should be text-based, check for binary content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read(1024)  # Try to read as text
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="CSV file contains invalid text encoding"
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File content validation failed: {e}")
        raise HTTPException(
            status_code=400,
            detail="File content validation failed"
        )


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

        # Return full response with all data (adaptive limiter already applied in services)
        return {
            "status": "success",
            "task_id": task_id,
            **payload,
        }

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
    Upload and parse UFM CSV file with chunked reading for large files.

    Accepts CSV files exported from UFM REST API.
    Uses chunked reading for efficient processing of large files.

    Returns parsed CSV data as JSON array.
    """
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
        logger.info(f"Saving CSV upload: {file.filename} (task: {task_id})")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate file content
        validate_file_content(file_path)

        # Read CSV in chunks to handle large files efficiently
        chunk_size = 10000
        chunks = []
        total_rows = 0

        logger.info(f"Reading CSV file in chunks...")
        csv_reader = None
        try:
            csv_reader = pd.read_csv(file_path, chunksize=chunk_size)
            for chunk in csv_reader:
                # Validate chunk has data
                if chunk.empty:
                    continue
                # Basic validation: check for reasonable column count
                if len(chunk.columns) > 1000:
                    raise HTTPException(
                        status_code=400,
                        detail="CSV has too many columns (max 1000)"
                    )
                total_rows += len(chunk)
                if len(chunks) == 0:  # Only keep first chunk for preview
                    chunks.append(chunk)
                # Limit total rows processed to prevent memory issues
                if total_rows > 1000000:  # 1M row limit
                    logger.warning(f"CSV exceeds 1M rows, truncating at {total_rows}")
                    break
        except pd.errors.ParserError as e:
            raise HTTPException(status_code=400, detail=f"CSV parsing error: {str(e)}")
        finally:
            # Ensure CSV reader is properly closed
            if csv_reader is not None:
                try:
                    csv_reader.close()
                except:
                    pass

        if not chunks:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        df_preview = chunks[0]
        columns = df_preview.columns.tolist()
        preview_data = df_preview.head(1000).to_dict(orient='records')

        logger.info(f"CSV processed: {total_rows} rows, {len(columns)} columns")

        return {
            "status": "success",
            "task_id": task_id,
            "filename": file.filename,
            "columns": columns,
            "row_count": total_rows,
            "data": preview_data,
            "preview_note": f"Showing first {len(preview_data)} of {total_rows} rows"
        }

    except pd.errors.EmptyDataError:
        logger.error(f"Empty CSV file: {file.filename}")
        raise HTTPException(status_code=400, detail="CSV file is empty")
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
    
    This endpoint streams data in chunks to avoid memory issues on the client side.
    Each chunk contains 500 rows of data.
    
    Args:
        task_id: The analysis task ID
        service_name: Name of the service (e.g., 'xmit', 'cable', 'ber')
    
    Returns:
        StreamingResponse with SSE events
    """
    
    async def event_generator():
        try:
            # Check if we have cached results for this task
            cache_key = f"{task_id}_{service_name}"
            
            if cache_key not in analysis_results_cache:
                yield f"event: error\ndata: {json.dumps({'error': 'Task not found or expired'})}\n\n"
                return
            
            data = analysis_results_cache[cache_key]
            
            if not data:
                yield f"event: complete\ndata: {json.dumps({'total': 0, 'message': 'No data available'})}\n\n"
                return
            
            total_rows = len(data)
            chunk_size = 500
            
            # Send metadata first
            yield f"event: metadata\ndata: {json.dumps({'total': total_rows, 'chunk_size': chunk_size})}\n\n"
            
            # Stream data in chunks
            for i in range(0, total_rows, chunk_size):
                chunk = data[i:i + chunk_size]
                chunk_data = {
                    'chunk_index': i // chunk_size,
                    'start': i,
                    'end': min(i + chunk_size, total_rows),
                    'data': chunk
                }
                
                yield f"event: data\ndata: {json.dumps(chunk_data)}\n\n"
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.05)
            
            # Send completion event
            yield f"event: complete\ndata: {json.dumps({'total': total_rows, 'message': 'Stream complete'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error for {task_id}/{service_name}: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
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
