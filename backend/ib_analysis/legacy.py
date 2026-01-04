from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any, Dict, Optional

from .config import get_config
from .core.operations import OperationManager
from .utils.logging import setup_logging
from .version import __version__

# Legacy global variables for compatibility
parsed_objects: Dict[str, Any] = {}
FILTERING_DF: Optional[Any] = None

# Legacy operation list
OP = [
    "xmit",         # 0
    "hca",          # 1
    "cable",        # 2
    "topo",         # 3
    "ber",          # 4
    "port",         # 5
    "pminfo",       # 6
    "cc",           # 7
    "brief",        # 8
    "nlastic",      # 9
    "histogram",    # 10
    "tableau"       # 11
]

OUT_FMT = ['csv', 'stdout', 'html', 'json']


def get_version() -> str:
    """Get version string for compatibility."""
    return __version__


class LegacyOperationManager:
    """Compatibility wrapper for the original operation management."""
    
    def __init__(self):
        self.config = get_config()
        self.operation_manager = OperationManager(self.config)
        setup_logging(level=self.config.logging.level)
    
    def execute_legacy_operation(
        self,
        operation: str,
        dir_a: str,
        dir_b: Optional[str] = None,
        **kwargs: Any
    ) -> int:
        """Execute operation using legacy interface."""
        
        warnings.warn(
            "Using legacy operation interface. Consider migrating to the new CLI.",
            DeprecationWarning,
            stacklevel=2
        )
        
        try:
            result = self.operation_manager.execute(
                operation=operation,
                dir_a=Path(dir_a),
                dir_b=Path(dir_b) if dir_b else None,
                **kwargs
            )
            
            # Print results for legacy compatibility
            if result.output_messages:
                for message in result.output_messages:
                    print(message)
            
            return result.exit_code
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


# Legacy functions for compatibility
def _(klass, varname=None, *constructor_args) -> Any:
    """Legacy object caching function."""
    warnings.warn(
        "Legacy object caching is deprecated. Use the new modular architecture.",
        DeprecationWarning,
        stacklevel=2
    )
    
    if (klass, constructor_args) in parsed_objects:
        obj = parsed_objects[(klass, constructor_args)]
    else:
        obj = klass(*constructor_args)
        parsed_objects[(klass, constructor_args)] = obj
    
    if varname:
        parsed_objects[varname] = obj
    
    return obj


def parse_default(ibdiagnet_dir: str):
    """Legacy parsing function."""
    warnings.warn(
        "parse_default is deprecated. Use the new OperationManager.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # This would need to import and use the original parsing logic
    # For now, return None to indicate this needs to be implemented
    # when integrating with existing code
    return None, None, None


def revert_filters():
    """Legacy filter reverting function."""
    warnings.warn(
        "revert_filters is deprecated. Filtering is now handled automatically.",
        DeprecationWarning,
        stacklevel=2
    )
    
    global FILTERING_DF
    FILTERING_DF = None


def process_command(input_args) -> int:
    """Legacy command processing function."""
    warnings.warn(
        "process_command is deprecated. Use the new CLI interface.",
        DeprecationWarning,
        stacklevel=2
    )
    
    manager = LegacyOperationManager()
    return manager.execute_legacy_operation(
        operation=input_args.operation,
        dir_a=input_args.dir_a,
        dir_b=getattr(input_args, 'dir_b', None),
        output_format=getattr(input_args, 'out_format', 'stdout'),
        lines=getattr(input_args, 'num_lines', 50),
        sort_column=getattr(input_args, 'sort', 0),
        extended_columns=getattr(input_args, 'extended_columns', []),
        overview=getattr(input_args, 'overview', False),
        check_anomalies=getattr(input_args, 'check', False),
        plot=getattr(input_args, 'plot', False),
        similar=getattr(input_args, 'similar', None),
    )


def setup_argparse():
    """Legacy argument parser setup."""
    import argparse
    import os
    
    warnings.warn(
        "setup_argparse is deprecated. Use the new CLI interface.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # This would need to import FILTER_MODES from the original filter module
    # For now, use a placeholder
    FILTER_MODES = ["column", "guid", "smart"]
    
    a_parser = argparse.ArgumentParser(
        description="Parse and analyse ibdiagnet files (Legacy Interface)",
        epilog="Note: This is the legacy interface. Use 'iba --help' for the new interface.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    a_parser.add_argument('-op', dest='operation', choices=OP, required=False,
                          help=f"Type of comparison to perform. Choose from: {', '.join(OP)}.")
    a_parser.add_argument('-i', '--interactive', action='store_true', 
                          help="Interactive mode, for faster results")

    a_parser.add_argument('dir_a', type=os.path.expanduser,
                          help='The path to the first ibdiagnet directory (mandatory)')
    a_parser.add_argument('dir_b', type=os.path.expanduser, nargs='?', default=None,
                          help='The path to the second ibdiagnet directory (optional)')
    a_parser.add_argument('--version', action='version', version=get_version())

    # Operations Parameters
    a_parser.add_argument('--output-format', '-o', dest='out_format', default="stdout", 
                          choices=OUT_FMT, metavar=f'{",".join(OUT_FMT)}',
                          help="Default value is 'stdout'.")
    a_parser.add_argument('--sort', '-s', type=int, default=0,
                          help="Sort the output based on the provided column number")
    a_parser.add_argument('--lines', '-n', type=int, default=50, metavar='<#lines>', 
                          dest='num_lines', help="Number of lines to print")
    a_parser.add_argument('--overview', action='store_true',
                          help="Show overview of all")
    a_parser.add_argument('--plot', action='store_true',
                          help="Show relation between counters")
    a_parser.add_argument('--check', action='store_true', 
                          help="Check for outliers")
    a_parser.add_argument('--html-file', default="nx.html", metavar='<out.html>', 
                          dest='html_file', help="output file for HTML")
    a_parser.add_argument('--html-label', '-hl', metavar='<xmit-wait>', 
                          dest='html_label', help="HTML label")
    a_parser.add_argument('--output-file', '-of', default="output.csv", 
                          metavar='<output.csv/.json>', dest='csv_file',
                          help="filename for output file")
    a_parser.add_argument('--extended-columns', '-e', default=[], 
                          type=lambda s: s.split(',') if s else [],
                          metavar='<column headers>', dest='extended_columns',
                          help="Additional columns to include")
    a_parser.add_argument('--filter-mode', '-fm', metavar='<column, guid>', 
                          dest='filter_mode', choices=FILTER_MODES,
                          help="Filter mode")
    a_parser.add_argument('--filter-param', '-fp', default=[], 
                          type=lambda s: s.split(',') if s else [],
                          metavar='<h1,=,0x1010fa23>', dest='filter_param',
                          help="Filter parameters")
    a_parser.add_argument('--filter', '-f', default=[], 
                          type=lambda s: s.split(',') if s else [],
                          metavar='<h1,=,0x1010fa23>', dest='filter',
                          help="Smart filter parameters")
    a_parser.add_argument('--tag', metavar='<key1=value1,key2=value2,...>', 
                          dest='tag', help="Tags for tableau operation")
    a_parser.add_argument('--similar', metavar='<column>', dest='similar',
                          help="Find statistically similar columns")
    a_parser.add_argument('--color-multiplain', '-cm', action='store_true', 
                          dest='color_plain', help="Colorful multiplain output")
    a_parser.add_argument('--aggregate-plains', '-ap', action='store_true', 
                          dest='agg_plains', help="Aggregate multiple plains data")

    return a_parser
