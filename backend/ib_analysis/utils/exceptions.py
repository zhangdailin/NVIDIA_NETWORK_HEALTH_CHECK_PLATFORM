"""Custom exceptions for IB Analysis toolkit."""

from __future__ import annotations


class IBAnalysisError(Exception):
    """Base exception for IB Analysis toolkit."""
    pass


class OperationError(IBAnalysisError):
    """Raised when an operation fails."""
    pass


class ParseError(IBAnalysisError):
    """Raised when parsing fails."""
    pass


class FilterError(IBAnalysisError):
    """Raised when filtering fails."""
    pass


class ConfigurationError(IBAnalysisError):
    """Raised when configuration is invalid."""
    pass


class DataValidationError(IBAnalysisError):
    """Raised when data validation fails."""
    pass
