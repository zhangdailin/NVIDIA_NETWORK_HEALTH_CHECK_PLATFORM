"""Configuration management for IB Analysis toolkit."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TableauConfig(BaseModel):
    """Configuration for Tableau integration."""
    
    base_dir: str = "/auto/sw/projects/performance/results/mongodb/IB_Hospital/"
    valid_tags: List[str] = Field(default_factory=lambda: [
        "cluster", "topology", "workload", "date", "user", "notes"
    ])


class OutputConfig(BaseModel):
    """Configuration for output formats and files."""
    
    default_format: str = "stdout"
    available_formats: List[str] = Field(default_factory=lambda: [
        "csv", "stdout", "html", "json"
    ])
    default_lines: int = 50
    default_html_file: str = "nx.html"
    default_csv_file: str = "output.csv"


class FilterConfig(BaseModel):
    """Configuration for filtering operations."""
    
    available_modes: List[str] = Field(default_factory=lambda: [
        "column", "guid", "smart"
    ])
    timeout_seconds: int = 300
    chunk_size: int = 1000


class PerformanceConfig(BaseModel):
    """Configuration for performance optimizations."""
    
    enable_caching: bool = True
    enable_progress_bars: bool = True
    enable_timeout_protection: bool = True
    max_processing_time: int = 300  # seconds
    chunk_size: int = 1000


class LoggingConfig(BaseModel):
    """Configuration for logging."""
    
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


class IBAnalysisConfig(BaseModel):
    """Main configuration for IB Analysis toolkit."""
    
    tableau: TableauConfig = Field(default_factory=TableauConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    filter: FilterConfig = Field(default_factory=FilterConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Operations configuration
    available_operations: List[str] = Field(default_factory=lambda: [
        "xmit", "hca", "cable", "topo", "ber", "port", 
        "pminfo", "cc", "brief", "nlastic", "histogram", "tableau"
    ])
    
    # Interactive mode configuration
    history_file: str = "~/.iba_history.txt"
    
    @classmethod
    def load_from_file(cls, config_path: Optional[Path] = None) -> IBAnalysisConfig:
        """Load configuration from file."""
        if config_path and config_path.exists():
            # In a real implementation, you'd load from YAML/TOML/JSON
            # For now, return default config
            pass
        return cls()
    
    @classmethod
    def load_from_env(cls) -> IBAnalysisConfig:
        """Load configuration from environment variables."""
        config = cls()
        
        # Override with environment variables if present
        if tableau_dir := os.getenv("IBA_TABLEAU_DIR"):
            config.tableau.base_dir = tableau_dir
        
        if log_level := os.getenv("IBA_LOG_LEVEL"):
            config.logging.level = log_level
        
        if log_file := os.getenv("IBA_LOG_FILE"):
            config.logging.file_path = log_file
        
        return config
    
    def get_history_file_path(self) -> Path:
        """Get the full path to the history file."""
        return Path(os.path.expanduser(self.history_file))


# Global configuration instance
_config: Optional[IBAnalysisConfig] = None


def get_config() -> IBAnalysisConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = IBAnalysisConfig.load_from_env()
    return _config


def set_config(config: IBAnalysisConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
