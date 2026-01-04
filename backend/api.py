from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
import zipfile
import tarfile
import pandas as pd
import uuid
from pathlib import Path
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import mimetypes

from ib_analysis.config import get_config
from ib_analysis.core.operations import OperationManager
from ib_analysis.health_score import calculate_health_score, health_report_to_dict

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

# Initialize OperationManager
config = get_config()
op_manager = OperationManager(config)

# Thread pool for parallel execution
executor = ThreadPoolExecutor(max_workers=4)


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


def validate_path_safety(base_path: Path, target_path: Path) -> None:
    """Ensure target_path is within base_path (prevent path traversal)."""
    try:
        base_resolved = base_path.resolve()
        target_resolved = target_path.resolve()

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

    elif file_path.suffix in {'.gz', '.tgz'} or file_path.name.endswith('.tar.gz'):
        with tarfile.open(file_path, 'r:gz') as tar_ref:
            # Validate all paths before extraction
            for member in tar_ref.getmembers():
                member_path = extract_dir / member.name
                validate_path_safety(extract_dir, member_path)

            tar_ref.extractall(extract_dir)
            logger.info(f"Extracted TAR.GZ: {len(tar_ref.getmembers())} files")

    else:
        raise HTTPException(status_code=400, detail="Unsupported archive format")


def run_analysis(operation: str, target_dir: Path, output_file: Path, output_format: str = "json", lines: int = 50):
    """Run ib_analysis operation and return result."""
    try:
        logger.info(f"Running {operation} analysis on {target_dir}")
        result = op_manager.execute(
            operation=operation,
            dir_a=target_dir,
            output_format=output_format,
            output_file=output_file,
            lines=lines,
        )
        logger.info(f"Completed {operation} analysis")
        return result
    except Exception as e:
        logger.error(f"Analysis {operation} failed: {e}", exc_info=True)
        raise


def load_json_file(file_path: Path) -> list:
    """Safely load JSON file with error handling."""
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return []


@router.post("/upload/ibdiagnet")
async def upload_ibdiagnet(file: UploadFile = File(...)):
    """
    Upload and analyze IBDiagnet archive with parallel processing.
    Includes security validation, automatic cleanup, and comprehensive error handling.
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

        # Define output files
        output_file = task_dir / "analysis_result.json"
        cable_file = task_dir / "cable.json"
        xmit_file = task_dir / "xmit.json"
        ber_file = task_dir / "ber.json"
        hca_file = task_dir / "hca.json"
        topo_file = task_dir / "network.html"

        # Run analyses in parallel (brief must run first, others can be parallel)
        logger.info("Starting brief analysis...")
        loop = asyncio.get_event_loop()
        brief_result = await loop.run_in_executor(
            executor,
            run_analysis,
            "brief",
            target_dir,
            output_file,
            "json"
        )

        # Run independent analyses in parallel
        logger.info("Starting parallel analyses (cable, xmit, ber, hca)...")
        parallel_tasks = [
            loop.run_in_executor(executor, run_analysis, "cable", target_dir, cable_file, "json"),
            loop.run_in_executor(executor, run_analysis, "xmit", target_dir, xmit_file, "json"),
            loop.run_in_executor(executor, run_analysis, "ber", target_dir, ber_file, "json"),
            loop.run_in_executor(executor, run_analysis, "hca", target_dir, hca_file, "json"),
        ]

        await asyncio.gather(*parallel_tasks, return_exceptions=True)
        logger.info("All analyses completed")

        # Load results with proper error handling
        analysis_data = load_json_file(output_file)
        cable_data = load_json_file(cable_file)
        xmit_data = load_json_file(xmit_file)
        ber_data = load_json_file(ber_file)
        hca_data = load_json_file(hca_file)

        # Calculate health score
        logger.info("Calculating health score...")
        health_report = calculate_health_score(
            analysis_data=analysis_data,
            cable_data=cable_data,
            xmit_data=xmit_data,
            ber_data=ber_data,
            hca_data=hca_data,
        )

        # Convert issues for topology visualization
        issues_dict = [
            {
                'severity': issue.severity.value,
                'category': issue.category,
                'description': issue.description,
                'node_guid': issue.node_guid,
                'port_number': issue.port_number,
                'weight': issue.weight,
                'details': issue.details,
            }
            for issue in health_report.issues
        ]

        # Generate topology visualization
        logger.info("Generating topology visualization...")
        await loop.run_in_executor(
            executor,
            lambda: op_manager.execute(
                operation="topo",
                dir_a=target_dir,
                output_format="html",
                output_file=topo_file,
                issues=issues_dict
            )
        )

        topo_url = f"/uploads/{task_id}/network.html" if topo_file.exists() else None

        logger.info(f"Analysis complete for task {task_id}")

        return {
            "status": "success",
            "task_id": task_id,
            "health": health_report_to_dict(health_report),
            "data": analysis_data,
            "cable_data": cable_data,
            "xmit_data": xmit_data,
            "ber_data": ber_data,
            "hca_data": hca_data,
            "topo_url": topo_url,
            "debug_stdout": "\n".join(brief_result.output_messages) if brief_result.output_messages else "",
            "debug_stderr": brief_result.error_message or ""
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Analysis failed for task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Clean up uploaded archive (keep extracted data and results)
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Cleaned up uploaded archive: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup archive: {e}")

@router.post("/upload/ufm-csv")
async def upload_ufm_csv(file: UploadFile = File(...)):
    """
    Upload and parse UFM CSV file with chunked reading for large files.
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

        # Read CSV in chunks to handle large files efficiently
        chunk_size = 10000
        chunks = []
        total_rows = 0

        logger.info(f"Reading CSV file in chunks...")
        for chunk in pd.read_csv(file_path, chunksize=chunk_size):
            total_rows += len(chunk)
            if len(chunks) == 0:  # Only keep first chunk for preview
                chunks.append(chunk)

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
                file_path.unlink()
                logger.info(f"Cleaned up CSV file: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup CSV: {e}")
