"""Utility modules for IB Analysis toolkit.

This package exposes the legacy utilities defined in the sibling module
``ib_analysis/utils.py`` so that imports like
``from src.ib_analysis.utils import _t`` continue to work.
"""

from pathlib import Path

# Dynamically execute the legacy utils.py into this package namespace
_legacy_utils_path = Path(__file__).resolve().parent.parent / "utils.py"
if _legacy_utils_path.exists():
    _code = _legacy_utils_path.read_text(encoding="utf-8")
    exec(_code, globals())


