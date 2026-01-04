"""Modern CLI interface for IB Analysis toolkit."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from .config import get_config
from .core.operations import OperationManager
from .core.interactive import InteractiveSession
from .utils.logging import setup_logging
from .version import __version__
from .pbar import disable_pbar, enable_pbar
import platform

app = typer.Typer(
    name="iba",
    help="Modern toolkit for analyzing InfiniBand network diagnostics",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


@app.command()
def analyze(
    operation: str = typer.Argument(
        help="Type of analysis to perform",
        metavar="OPERATION"
    ),
    dir_a: Path = typer.Argument(
        help="Path to the ibdiagnet directory",
        exists=True,
        file_okay=False,
        dir_okay=True,
        metavar="DIRECTORY"
    ),
    dir_b: Optional[Path] = typer.Argument(
        None,
        help="Path to second ibdiagnet directory for comparison",
        exists=True,
        file_okay=False,
        dir_okay=True,
        metavar="DIRECTORY"
    ),
    # Output options
    output_format: str = typer.Option(
        "stdout",
        "--format", "-f",
        help="Output format",
        metavar="FORMAT"
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path",
        metavar="FILE"
    ),
    # Display options
    lines: int = typer.Option(
        50,
        "--lines", "-n",
        help="Number of lines to display (-1 for all)",
        metavar="N"
    ),
    sort_column: int = typer.Option(
        0,
        "--sort", "-s",
        help="Sort by column number (0 to disable)",
        metavar="COL"
    ),
    extended_columns: List[str] = typer.Option(
        [],
        "--extend", "-e",
        help="Additional columns to include",
        metavar="COLUMNS"
    ),
    # Analysis options
    overview: bool = typer.Option(
        False,
        "--overview",
        help="Show overview instead of detailed data"
    ),
    check_anomalies: bool = typer.Option(
        False,
        "--check",
        help="Perform anomaly detection"
    ),
    plot: bool = typer.Option(
        False,
        "--plot",
        help="Show relationship plots"
    ),
    similar: Optional[str] = typer.Option(
        None,
        "--similar",
        help="Find statistically similar columns",
        metavar="COLUMN"
    ),
    # Filter options
    filter_mode: Optional[str] = typer.Option(
        None,
        "--filter-mode",
        help="Filter mode (column, guid, smart)",
        metavar="MODE"
    ),
    filter_params: List[str] = typer.Option(
        [],
        "--filter",
        help="Filter parameters",
        metavar="PARAMS"
    ),
    # HTML specific options
    html_label: Optional[str] = typer.Option(
        None,
        "--html-label",
        help="Label for HTML output",
        metavar="LABEL"
    ),
    # Tableau options
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        help="Tags for tableau operation (key1=value1,key2=value2)",
        metavar="TAGS"
    ),
    # Display options
    color_multiplain: bool = typer.Option(
        False,
        "--color-multiplain",
        help="Colorful multiplain output"
    ),
    aggregate_plains: bool = typer.Option(
        False,
        "--aggregate-plains", 
        help="Aggregate multiple plains data"
    ),
    # Logging
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose logging"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet", "-q",
        help="Suppress non-error output"
    ),
) -> None:
    """Analyze InfiniBand network diagnostics."""
    
    config = get_config()
    
    # Setup logging
    log_level = "DEBUG" if verbose else "ERROR" if quiet else config.logging.level
    setup_logging(level=log_level)
    
    # Validate operation
    if operation not in config.available_operations:
        console.print(f"[red]Error:[/red] Unknown operation '{operation}'")
        console.print(f"Available operations: {', '.join(config.available_operations)}")
        raise typer.Exit(1)
    
    # Validate output format
    if output_format not in config.output.available_formats:
        console.print(f"[red]Error:[/red] Unknown output format '{output_format}'")
        console.print(f"Available formats: {', '.join(config.output.available_formats)}")
        raise typer.Exit(1)
    
    try:
        # Create operation manager
        op_manager = OperationManager(config)

        # Avoid overlapping progress outputs (tqdm vs rich) on Windows terminals only
        is_windows = platform.system().lower().startswith('win')
        if is_windows:
            disable_pbar()
        try:
            # Show progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing data...", total=None)

                # Execute operation
                result = op_manager.execute(
                    operation=operation,
                    dir_a=dir_a,
                    dir_b=dir_b,
                    output_format=output_format,
                    output_file=output_file,
                    lines=lines,
                    sort_column=sort_column,
                    extended_columns=extended_columns,
                    overview=overview,
                    check_anomalies=check_anomalies,
                    plot=plot,
                    similar=similar,
                    filter_mode=filter_mode,
                    filter_params=filter_params,
                    html_label=html_label,
                    tag=tag,
                    color_multiplain=color_multiplain,
                    aggregate_plains=aggregate_plains,
                )

                progress.update(task, completed=True)
        finally:
            # Re-enable pbar state for other entrypoints (e.g., interactive)
            if is_windows:
                enable_pbar()
        
        # Display results
        if result.output_messages:
            for message in result.output_messages:
                try:
                    # Render ANSI escape sequences correctly (plotext output, custom color codes)
                    if isinstance(message, str):
                        console.print(Text.from_ansi(message))
                    else:
                        console.print(message)
                except Exception:
                    console.print(message)
        
        if result.files_created:
            console.print("\n[green]Files created:[/green]")
            for file_path in result.files_created:
                console.print(f"  • {file_path}")
        
        if result.exit_code != 0:
            raise typer.Exit(result.exit_code)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def interactive(
    dir_a: Optional[Path] = typer.Argument(
        None,
        help="Default ibdiagnet directory for interactive mode",
        exists=True,
        file_okay=False,
        dir_okay=True,
        metavar="DIRECTORY"
    ),
    dir_b: Optional[Path] = typer.Argument(
        None,
        help="Default second directory for comparisons",
        exists=True,
        file_okay=False,
        dir_okay=True,
        metavar="DIRECTORY"
    ),
) -> None:
    """Start interactive analysis session."""
    
    config = get_config()
    setup_logging(level=config.logging.level)
    
    console.print(Panel.fit(
        "[bold blue]IB Analysis Interactive Mode[/bold blue]\n"
        "Type 'help' for commands, 'exit' to quit",
        border_style="blue"
    ))
    
    try:
        session = InteractiveSession(config, console)
        session.run(default_dir_a=dir_a, default_dir_b=dir_b)
    except KeyboardInterrupt:
        console.print("\n[yellow]Session ended[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def operations() -> None:
    """List available operations."""
    
    config = get_config()
    
    table = Table(title="Available Operations")
    table.add_column("Operation", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    
    operation_descriptions = {
        "xmit": "Analyze transmission data and wait times",
        "hca": "Analyze Host Channel Adapter information", 
        "cable": "Analyze cable and port information",
        "topo": "Analyze network topology",
        "ber": "Analyze Bit Error Rate data",
        "port": "Analyze port statistics",
        "pminfo": "Analyze Performance Manager information",
        "cc": "Analyze Congestion Control data",
        "brief": "Generate brief analysis summary",
        "nlastic": "Analyze network elasticity",
        "histogram": "Generate buffer occupancy histograms",
        "tableau": "Export data for Tableau visualization",
    }
    
    for op in config.available_operations:
        description = operation_descriptions.get(op, "No description available")
        table.add_row(op, description)
    
    console.print(table)


@app.command()
def version() -> None:
    """Show version information."""
    
    console.print(f"IB Analysis Toolkit v{__version__}")
    console.print("Modern toolkit for analyzing InfiniBand network diagnostics")
    console.print("Copyright © NVIDIA Corporation")


@app.callback()
def main(
    ctx: typer.Context,
    version_flag: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit"
    ),
) -> None:
    """
    Modern toolkit for analyzing and visualizing InfiniBand network diagnostics.
    
    This toolkit is designed to analyze ibdiagnet files, offering insights into
    the health and performance of your InfiniBand network.
    """
    
    if version_flag:
        console.print(f"IB Analysis Toolkit v{__version__}")
        raise typer.Exit()


def cli_main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    cli_main()
