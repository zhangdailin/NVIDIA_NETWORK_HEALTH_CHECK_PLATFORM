"""Interactive session management."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.panel import Panel

from ..config import IBAnalysisConfig
from .operations import OperationManager


class InteractiveSession:
    """Manages interactive analysis sessions."""
    
    def __init__(self, config: IBAnalysisConfig, console: Console):
        self.config = config
        self.console = console
        self.operation_manager = OperationManager(config)
        self.history: List[str] = []
        self.default_dir_a: Optional[Path] = None
        self.default_dir_b: Optional[Path] = None
    
    def run(
        self,
        default_dir_a: Optional[Path] = None,
        default_dir_b: Optional[Path] = None,
    ) -> None:
        """Run the interactive session."""
        
        self.default_dir_a = default_dir_a
        self.default_dir_b = default_dir_b
        
        # Load command history
        self._load_history()
        
        self.console.print("[green]Interactive mode started. Type 'help' for commands.[/green]")
        
        if default_dir_a:
            self.console.print(f"Default directory A: {default_dir_a}")
        if default_dir_b:
            self.console.print(f"Default directory B: {default_dir_b}")
        
        try:
            while True:
                try:
                    # Get user input
                    prompt_text = self._get_prompt()
                    user_input = Prompt.ask(prompt_text).strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle special commands
                    if user_input.lower() in ['exit', 'quit', 'q']:
                        break
                    elif user_input.lower() in ['help', 'h', '?']:
                        self._show_help()
                        continue
                    elif user_input.lower() in ['clear', 'cls', 'c']:
                        self.console.clear()
                        continue
                    elif user_input.lower() == 'history':
                        self._show_history()
                        continue
                    elif user_input.lower() == 'operations':
                        self._show_operations()
                        continue
                    elif user_input.startswith('set '):
                        self._handle_set_command(user_input[4:])
                        continue
                    
                    # Add to history
                    self.history.append(user_input)
                    self._save_history()
                    
                    # Parse and execute command
                    self._execute_command(user_input)
                    
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Use 'exit' to quit[/yellow]")
                    continue
                except EOFError:
                    break
        
        finally:
            self.console.print("[green]Interactive session ended.[/green]")
    
    def _get_prompt(self) -> str:
        """Generate the command prompt."""
        if self.default_dir_a:
            dir_name = self.default_dir_a.name
            return f"[bold cyan]iba[/bold cyan] ([green]{dir_name}[/green])"
        return "[bold cyan]iba[/bold cyan]"
    
    def _execute_command(self, command: str) -> None:
        """Execute a command."""
        try:
            # Parse command
            parts = shlex.split(command)
            if not parts:
                return
            
            operation = parts[0]
            args = parts[1:]
            
            # Validate operation
            if operation not in self.config.available_operations:
                self.console.print(f"[red]Unknown operation:[/red] {operation}")
                self.console.print(f"Available operations: {', '.join(self.config.available_operations)}")
                return
            
            # Parse directories from args or use defaults
            dir_a = None
            dir_b = None
            
            if args:
                dir_a = Path(args[0])
                if len(args) > 1:
                    dir_b = Path(args[1])
            else:
                dir_a = self.default_dir_a
                dir_b = self.default_dir_b
            
            if not dir_a:
                self.console.print("[red]Error:[/red] No directory specified and no default set")
                return
            
            # Execute operation
            result = self.operation_manager.execute(
                operation=operation,
                dir_a=dir_a,
                dir_b=dir_b,
            )
            
            # Display results
            if result.output_messages:
                for message in result.output_messages:
                    self.console.print(message)
            
            if result.files_created:
                self.console.print("\n[green]Files created:[/green]")
                for file_path in result.files_created:
                    self.console.print(f"  • {file_path}")
            
            if result.error_message:
                self.console.print(f"[red]Error:[/red] {result.error_message}")
        
        except Exception as e:
            self.console.print(f"[red]Error executing command:[/red] {e}")
    
    def _show_help(self) -> None:
        """Show help information."""
        help_text = """
[bold]Available Commands:[/bold]

[cyan]Operations:[/cyan]
  {operations}

[cyan]Special Commands:[/cyan]
  help, h, ?        Show this help
  operations        List available operations  
  history           Show command history
  clear, cls, c     Clear screen
  set <key>=<value> Set session variables
  exit, quit, q     Exit interactive mode

[cyan]Examples:[/cyan]
  xmit                    Run xmit analysis on default directory
  xmit /path/to/dir       Run xmit analysis on specified directory  
  hca /path/a /path/b     Compare HCA data between two directories
  set dir_a=/path/to/dir  Set default directory A

[cyan]Session Variables:[/cyan]
  dir_a={dir_a}
  dir_b={dir_b}
        """.format(
            operations="  " + "  ".join(self.config.available_operations),
            dir_a=self.default_dir_a or "not set",
            dir_b=self.default_dir_b or "not set",
        )
        
        self.console.print(Panel(help_text.strip(), title="Help", border_style="blue"))
    
    def _show_operations(self) -> None:
        """Show available operations."""
        table = Table(title="Available Operations")
        table.add_column("Operation", style="cyan")
        table.add_column("Description", style="white")
        
        descriptions = {
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
        
        for op in self.config.available_operations:
            desc = descriptions.get(op, "No description available")
            table.add_row(op, desc)
        
        self.console.print(table)
    
    def _show_history(self) -> None:
        """Show command history."""
        if not self.history:
            self.console.print("[yellow]No command history[/yellow]")
            return
        
        self.console.print("[bold]Command History:[/bold]")
        for i, cmd in enumerate(self.history[-10:], 1):  # Show last 10 commands
            self.console.print(f"  {i:2}. {cmd}")
    
    def _handle_set_command(self, args: str) -> None:
        """Handle set command for session variables."""
        if '=' not in args:
            self.console.print("[red]Error:[/red] Use format: set key=value")
            return
        
        key, value = args.split('=', 1)
        key = key.strip()
        value = value.strip()
        
        if key == 'dir_a':
            path = Path(value)
            if path.exists() and path.is_dir():
                self.default_dir_a = path
                self.console.print(f"[green]Set dir_a to:[/green] {path}")
            else:
                self.console.print(f"[red]Error:[/red] Directory does not exist: {path}")
        elif key == 'dir_b':
            path = Path(value)
            if path.exists() and path.is_dir():
                self.default_dir_b = path
                self.console.print(f"[green]Set dir_b to:[/green] {path}")
            else:
                self.console.print(f"[red]Error:[/red] Directory does not exist: {path}")
        else:
            self.console.print(f"[red]Error:[/red] Unknown variable: {key}")
    
    def _load_history(self) -> None:
        """Load command history from file."""
        history_file = self.config.get_history_file_path()
        try:
            if history_file.exists():
                with history_file.open('r', encoding='utf-8') as f:
                    self.history = [line.strip() for line in f if line.strip()]
        except Exception:
            # Ignore errors when loading history
            pass
    
    def _save_history(self) -> None:
        """Save command history to file."""
        history_file = self.config.get_history_file_path()
        try:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            with history_file.open('w', encoding='utf-8') as f:
                # Save last 100 commands
                for cmd in self.history[-100:]:
                    f.write(cmd + '\n')
        except Exception:
            # Ignore errors when saving history
            pass
