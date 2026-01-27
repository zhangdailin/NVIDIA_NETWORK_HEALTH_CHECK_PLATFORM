"""Adaptive data limiter with explicit configuration only."""

import os
from typing import List, Dict, Any


def calculate_adaptive_limit(records: List[Dict[str, Any]]) -> int:
    """
    Calculate row limit based on explicit configuration only.

    Uses MAX_PREVIEW_ROWS when provided:
      - unset/empty -> return all rows
      - <= 0 -> return all rows
      - > 0 -> return up to that many rows
    """
    if not records:
        return 0

    raw_limit = os.getenv("MAX_PREVIEW_ROWS")
    if raw_limit is None or str(raw_limit).strip() == "":
        return len(records)

    try:
        max_preview_rows = int(raw_limit)
    except ValueError:
        return len(records)

    if max_preview_rows <= 0:
        return len(records)

    return min(len(records), max_preview_rows)


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
