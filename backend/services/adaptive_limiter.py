"""Adaptive data limiter that intelligently determines row limits based on data characteristics."""

import os
import sys
from typing import List, Dict, Any

# Target memory size for JSON response (in bytes)
TARGET_RESPONSE_SIZE = 2 * 1024 * 1024  # 2MB uncompressed (will be ~200KB with gzip)

def calculate_adaptive_limit(records: List[Dict[str, Any]], default_limit: int = 5000) -> int:
    """
    Calculate an adaptive row limit based on the actual data size.

    Args:
        records: List of record dictionaries
        default_limit: Default limit if calculation fails

    Returns:
        Optimal number of rows to return
    """
    if not records:
        return default_limit

    # Get configured max limit (0 = unlimited)
    max_preview_rows = int(os.getenv("MAX_PREVIEW_ROWS", "0"))
    if max_preview_rows > 0:
        # User has set a specific limit, respect it
        return min(len(records), max_preview_rows)

    # Sample first few rows to estimate average row size
    sample_size = min(10, len(records))
    sample_records = records[:sample_size]

    try:
        # Estimate size of sample records
        import json
        sample_json = json.dumps(sample_records)
        sample_bytes = sys.getsizeof(sample_json)

        # Calculate average bytes per row
        avg_bytes_per_row = sample_bytes / sample_size

        # Calculate how many rows fit in target size
        optimal_rows = int(TARGET_RESPONSE_SIZE / avg_bytes_per_row)

        # Apply reasonable bounds
        min_rows = 500   # Always return at least 500 rows if available
        max_rows = 5000  # Cap at 5000 rows to prevent memory issues

        optimal_rows = max(min_rows, min(optimal_rows, max_rows))

        # Return the smaller of optimal or actual data size
        return min(len(records), optimal_rows)

    except Exception:
        # If estimation fails, use default
        return min(len(records), default_limit)


def apply_adaptive_limit(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply adaptive limiting to a list of records.

    Args:
        records: List of record dictionaries

    Returns:
        Limited list of records
    """
    if not records:
        return records

    limit = calculate_adaptive_limit(records)

    if limit >= len(records):
        return records

    return records[:limit]
