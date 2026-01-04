"""Operation management and execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import os
from datetime import datetime

import pandas as pd
from tabulate import tabulate

from ..config import IBAnalysisConfig
from ..utils.exceptions import IBAnalysisError, OperationError
from ..graph import Graph
from ..ber import Ber
from ..hca import HcaManager
from ..xmit import Xmit
from ..port import Port
from ..pminfo import PMInfo
from ..cable import CableManager
from ..cc import CongestionControl
from ..histogram import Histogram
from ..ibpm import IbPm

logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
    """Result of an operation execution."""
    
    exit_code: int = 0
    output_messages: List[str] = field(default_factory=list)
    files_created: List[Path] = field(default_factory=list)
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class OperationManager:
    """Manages and executes analysis operations."""
    
    def __init__(self, config: IBAnalysisConfig):
        self.config = config
        self._operation_cache: Dict[str, Any] = {}
    
    def execute(
        self,
        operation: str,
        dir_a: Path,
        dir_b: Optional[Path] = None,
        output_format: str = "stdout",
        output_file: Optional[Path] = None,
        lines: int = 50,
        sort_column: int = 0,
        extended_columns: Optional[List[str]] = None,
        overview: bool = False,
        check_anomalies: bool = False,
        plot: bool = False,
        similar: Optional[str] = None,
        filter_mode: Optional[str] = None,
        filter_params: Optional[List[str]] = None,
        html_label: Optional[str] = None,
        tag: Optional[str] = None,
        color_multiplain: bool = False,
        aggregate_plains: bool = False,
        **kwargs: Any,
    ) -> OperationResult:
        """Execute an analysis operation."""
        
        logger.info(f"Executing operation: {operation}")
        logger.debug(f"Parameters: dir_a={dir_a}, dir_b={dir_b}, format={output_format}")
        
        try:
            # Validate inputs
            self._validate_operation_inputs(
                operation, dir_a, dir_b, output_format, extended_columns
            )
            
            # Load and parse data
            parsed_data = self._load_data(dir_a, dir_b)
            
            # Apply filters if specified
            if filter_mode or filter_params:
                parsed_data = self._apply_filters(
                    parsed_data, filter_mode, filter_params or []
                )
            
            # Execute specific operation
            result = self._execute_operation(
                operation=operation,
                parsed_data=parsed_data,
                output_format=output_format,
                output_file=output_file,
                lines=lines,
                sort_column=sort_column,
                extended_columns=extended_columns or [],
                overview=overview,
                check_anomalies=check_anomalies,
                plot=plot,
                similar=similar,
                html_label=html_label,
                tag=tag,
                color_multiplain=color_multiplain,
                aggregate_plains=aggregate_plains,
                **kwargs,
            )
            
            logger.info(f"Operation {operation} completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Operation {operation} failed: {e}")
            return OperationResult(
                exit_code=1,
                error_message=str(e),
                output_messages=[f"Error: {e}"]
            )
    
    def _validate_operation_inputs(
        self,
        operation: str,
        dir_a: Path,
        dir_b: Optional[Path],
        output_format: str,
        extended_columns: Optional[List[str]],
    ) -> None:
        """Validate operation inputs."""
        
        if operation not in self.config.available_operations:
            raise OperationError(f"Unknown operation: {operation}")
        
        if not dir_a.exists() or not dir_a.is_dir():
            raise OperationError(f"Directory does not exist: {dir_a}")
        
        if dir_b and (not dir_b.exists() or not dir_b.is_dir()):
            raise OperationError(f"Directory does not exist: {dir_b}")
        
        if output_format not in self.config.output.available_formats:
            raise OperationError(f"Unknown output format: {output_format}")
    
    def _load_data(self, dir_a: Path, dir_b: Optional[Path] = None) -> Dict[str, Any]:
        """Load and parse data from directories."""
        
        logger.info("Loading data...")
        
        # Build core objects from dir_a now (dir_b support can be added later)
        graph = Graph(str(dir_a))
        
        # Initialize managers needed by topo overview (PMInfo is used inside Graph.print_overview)
        try:
            hca_m = HcaManager(ib_dir=str(dir_a), g=graph)
            ibpm = IbPm(str(dir_a))
            pminfo = PMInfo(ib_dir=str(dir_a), g=graph, hca_m=hca_m, ib_pm=ibpm)
            graph.set_pminfo(pminfo)
        except Exception:
            # If PMInfo cannot be initialized (e.g., missing files), continue without it
            pass
        
        return {
            "dir_a": str(dir_a),
            "dir_b": str(dir_b) if dir_b else None,
            "graph": graph,
        }
    
    def _apply_filters(
        self,
        parsed_data: Dict[str, Any],
        filter_mode: Optional[str],
        filter_params: List[str],
    ) -> Dict[str, Any]:
        """Apply filters to parsed data."""
        
        if not filter_mode or not filter_params:
            return parsed_data
        
        logger.info(f"Applying filters: mode={filter_mode}, params={filter_params}")
        
        # TODO: Implement filtering logic
        # This would integrate with the existing filter.py module
        
        return parsed_data
    
    def _execute_operation(
        self,
        operation: str,
        parsed_data: Dict[str, Any],
        **kwargs: Any,
    ) -> OperationResult:
        """Execute the specific operation."""
        
        operation_methods = {
            "xmit": self._execute_xmit,
            "hca": self._execute_hca,
            "cable": self._execute_cable,
            "topo": self._execute_topo,
            "ber": self._execute_ber,
            "port": self._execute_port,
            "pminfo": self._execute_pminfo,
            "cc": self._execute_cc,
            "brief": self._execute_brief,
            "nlastic": self._execute_nlastic,
            "histogram": self._execute_histogram,
            "tableau": self._execute_tableau,
        }
        
        method = operation_methods.get(operation)
        if not method:
            raise OperationError(f"Operation not implemented: {operation}")
        
        return method(parsed_data, **kwargs)
    
    def _execute_xmit(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute xmit operation."""
        try:
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            overview: bool = kwargs.get("overview", False)
            check_anomalies: bool = kwargs.get("check_anomalies", False)
            plot: bool = kwargs.get("plot", False)
            similar: Optional[str] = kwargs.get("similar")
            color_multiplain: bool = kwargs.get("color_multiplain", False)
            aggregate_plains: bool = kwargs.get("aggregate_plains", False)

            # Build managers
            hca_m = HcaManager(ib_dir=dir_a, g=graph)
            xmit = Xmit(ib_dir=dir_a, g=graph, hca_m=hca_m)

            messages: List[str] = []
            files_created: List[Path] = []

            # Decide content to render
            if overview:
                messages = xmit.print_overview(extended_columns=extended_columns)
            elif plot:
                messages = xmit.print_plot(extended_columns=extended_columns)
            elif check_anomalies:
                messages = xmit.print_anomalies(sort=sort_column, num_lines=lines, extended_columns=extended_columns)
            else:
                messages = xmit.table(
                    sort=sort_column,
                    num_lines=lines,
                    extended_columns=extended_columns,
                    similar=similar,
                    color_plains=color_multiplain,
                    agg_plains=aggregate_plains,
                )

            # Handle output format
            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                if check_anomalies:
                    # Export anomalies when requested
                    df_anom = xmit.get_anomalies(nlastic=False)
                    from ..xmit import Xmit as XmitClass
                    base_cols = [c for c in XmitClass.COLUMNS_TO_PRINT_ANOMALY if c in df_anom.columns]
                    keep_cols = [c for c in (extended_columns or []) if c in df_anom.columns]
                    columns = base_cols + keep_cols
                    out_path = Path(output_file) if output_file else Path.cwd() / "xmit_anomalies.csv"
                    df_out = df_anom.copy()
                    if 'Index' in XmitClass.COLUMNS_TO_PRINT_ANOMALY and 'Index' not in df_out.columns:
                        df_out['Index'] = range(1, df_out.shape[0] + 1)
                    if columns:
                        df_out = df_out[columns]
                    df_out.to_csv(str(out_path), index=False)
                    return OperationResult(output_messages=[f"Saved CSV: {out_path}"], files_created=[out_path])
                else:
                    # Export nodes/edges CSV joined with xmit
                    nodes_path = Path(output_file) if output_file else Path.cwd() / "nodes.csv"
                    edges_path = nodes_path if nodes_path.suffix.lower() == ".csv" else Path.cwd() / "edges.csv"
                    created = xmit.to_csv(g=graph, nodes_filename=str(nodes_path), edges_filename=str(edges_path), extended_columns=extended_columns)
                    files_created = [Path(p) for p in created]
                    return OperationResult(output_messages=[f"Saved CSV: {', '.join(map(str, files_created))}"], files_created=files_created)
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "xmit.html"
                html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>Xmit Report</title></head>
<body><h2>Xmit Report</h2>{html_body}</body></html>
"""
                html_path.write_text(html, encoding="utf-8")
                files_created = [html_path]
                return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=files_created)
            elif fmt == "json":
                json_path = Path(output_file) if output_file else Path.cwd() / "xmit.json"
                df = xmit.df.copy()
                if lines > 0:
                    df = df.head(lines)
                df.to_json(str(json_path), orient="records")
                files_created = [json_path]
                return OperationResult(output_messages=[f"Saved JSON: {json_path}"], files_created=files_created)

            # Default stdout
            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"XMIT execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_hca(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute hca operation."""
        try:
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            overview: bool = kwargs.get("overview", False)
            check_anomalies: bool = kwargs.get("check_anomalies", False)
            plot: bool = kwargs.get("plot", False)

            hca = HcaManager(ib_dir=dir_a, g=graph)

            if overview:
                messages = hca.print_overview(extended_columns=extended_columns)
            elif plot:
                messages = hca.print_plot(extended_columns=extended_columns)
            elif check_anomalies:
                messages = hca.print_anomalies(sort=sort_column, num_lines=lines, extended_columns=extended_columns)
            else:
                messages = hca.table(num_lines=lines, sort=sort_column, extended_columns=extended_columns)

            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                csv_path = Path(output_file) if output_file else Path.cwd() / "hca.csv"
                if check_anomalies:
                    df_anom = hca.get_anomalies()
                    from ..hca import HcaManager as HClass
                    base_cols = [c for c in (HClass.COLUMNS_TO_PRINT + [IBH_ANOMALY_AGG_COL]) if c in df_anom.columns]
                    keep_cols = [c for c in (extended_columns or []) if c in df_anom.columns]
                    columns = base_cols + keep_cols
                    df_out = df_anom.copy()
                    if 'Index' in base_cols and 'Index' not in df_out.columns:
                        df_out['Index'] = range(1, df_out.shape[0] + 1)
                    if columns:
                        df_out = df_out[columns]
                    df_out.to_csv(str(csv_path), index=False)
                    return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=[csv_path])
                created = hca.to_csv(csv_filename=str(csv_path), extended_columns=extended_columns)
                files_created = [Path(p) for p in created]
                return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=files_created)
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "hca.html"
                html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>HCA Report</title></head>
<body><h2>HCA Report</h2>{html_body}</body></html>
"""
                html_path.write_text(html, encoding="utf-8")
                return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=[html_path])
            elif fmt == "json":
                json_path = Path(output_file) if output_file else Path.cwd() / "hca.json"
                df = hca.df.copy()
                if lines > 0:
                    df = df.head(lines)
                df.to_json(str(json_path), orient="records")
                return OperationResult(output_messages=[f"Saved JSON: {json_path}"], files_created=[json_path])

            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"HCA execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_cable(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute cable operation."""
        try:
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            overview: bool = kwargs.get("overview", False)
            check_anomalies: bool = kwargs.get("check_anomalies", False)

            # Build dependencies
            hca_m = HcaManager(ib_dir=dir_a, g=graph)
            xmit = Xmit(ib_dir=dir_a, g=graph, hca_m=hca_m)
            port_m = Port(ib_dir=dir_a, g=graph, pminfo=None)
            cable = CableManager(ib_dir=dir_a, g=graph, port_m=port_m, xmit_m=xmit)

            if overview:
                messages = cable.print_overview(extended_columns=extended_columns)
            elif check_anomalies:
                messages = cable.print_anomalies(sort=sort_column, num_lines=lines, extended_columns=extended_columns)
            else:
                messages = cable.table(num_lines=lines, sort=sort_column, extended_columns=extended_columns)

            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                csv_path = Path(output_file) if output_file else Path.cwd() / "cables.csv"
                if check_anomalies:
                    # Export anomalies when requested
                    df_anom = cable.get_anomalies()
                    # Select columns similar to print_anomalies output
                    base_cols = [c for c in CableManager.COLUMNS_TO_PRINT_ANOMALY if c in df_anom.columns]
                    keep_cols = [c for c in (extended_columns or []) if c in df_anom.columns]
                    columns = base_cols + keep_cols
                    df_out = df_anom.copy()
                    if 'Index' in CableManager.COLUMNS_TO_PRINT_ANOMALY and 'Index' not in df_out.columns:
                        df_out['Index'] = range(1, df_out.shape[0] + 1)
                    if columns:
                        df_out = df_out[columns]
                    df_out.to_csv(str(csv_path), index=False)
                    return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=[csv_path])
                else:
                    # If filename ends with *_pairs.csv export pair-view
                    if csv_path.name.endswith('_pairs.csv'):
                        created = cable.to_pairs_csv(csv_filename=str(csv_path))
                    else:
                        created = cable.to_csv(csv_filename=str(csv_path), extended_columns=extended_columns)
                    return OperationResult(output_messages=[f"Saved CSV: {', '.join(created)}"], files_created=[Path(p) for p in created])
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "cable.html"
                html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>Cable Report</title></head>
<body><h2>Cable Report</h2>{html_body}</body></html>
"""
                html_path.write_text(html, encoding="utf-8")
                return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=[html_path])
            elif fmt == "json":
                json_path = Path(output_file) if output_file else Path.cwd() / "cable.json"
                df = cable.df.copy()
                if lines > 0:
                    df = df.head(lines)
                df.to_json(str(json_path), orient="records")
                return OperationResult(output_messages=[f"Saved JSON: {json_path}"], files_created=[json_path])

            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"CABLE execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_topo(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute topo operation."""
        try:
            graph: Graph = parsed_data.get("graph")
            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            overview: bool = kwargs.get("overview", False)
            check_anomalies: bool = kwargs.get("check_anomalies", False)
            issues: Optional[List[Dict]] = kwargs.get("issues")

            if check_anomalies:
                messages = graph.print_anomalies(sort=sort_column, num_lines=lines, extended_columns=extended_columns)
            else:
                messages = graph.print_overview(extended_columns=extended_columns)

            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                created = graph.to_csv()
                return OperationResult(output_messages=["Saved CSV: edges.csv"], files_created=[Path(p) for p in created])
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "nx.html"
                created = graph.to_html(filename=str(html_path), issues=issues)
                return OperationResult(output_messages=[f"Saved HTML: {created[0]}"], files_created=[Path(created[0])])

            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"TOPO execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_ber(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute ber operation."""
        try:
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            overview: bool = kwargs.get("overview", False)
            check_anomalies: bool = kwargs.get("check_anomalies", False)
            plot: bool = kwargs.get("plot", False)

            ber = Ber(ib_dir=dir_a, g=graph, use_net_dump_ext=True)

            messages: List[str] = []
            files_created: List[Path] = []

            # Decide content to render
            if overview:
                messages = ber.print_overview(extended_columns=extended_columns)
            elif plot:
                messages = ber.print_plot(extended_columns=extended_columns)
            elif check_anomalies:
                messages = ber.print_anomalies(sort=sort_column, num_lines=lines, extended_columns=extended_columns)
            else:
                messages = ber.table(num_lines=lines, sort=sort_column, extended_columns=extended_columns)

            # Handle output format
            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                csv_path = Path(output_file) if output_file else Path.cwd() / "ber.csv"
                if check_anomalies:
                    from ..ber import Ber as BerClass
                    df = ber.df.copy()
                    from ..anomaly import merge_anomalies, get_high_ber_anomalies, get_unusual_ber_anomalies
                    df_anom = merge_anomalies(df, [get_high_ber_anomalies(df.copy()), get_unusual_ber_anomalies(df.copy())])
                    base_cols = [c for c in BerClass.COLUMNS_TO_PRINT_ANOMALY if c in df_anom.columns]
                    keep_cols = [c for c in (extended_columns or []) if c in df_anom.columns]
                    columns = base_cols + keep_cols
                    df_out = df_anom.copy()
                    if 'Index' in BerClass.COLUMNS_TO_PRINT_ANOMALY and 'Index' not in df_out.columns:
                        df_out['Index'] = range(1, df_out.shape[0] + 1)
                    if columns:
                        df_out = df_out[columns]
                    df_out.to_csv(str(csv_path), index=False)
                    return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=[csv_path])
                created = ber.to_csv(csv_filename=str(csv_path), extended_columns=extended_columns)
                files_created = [Path(p) for p in created]
                return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=files_created)
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "ber.html"
                try:
                    # Prefer the same content as shown in stdout for consistency
                    html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                    html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>BER Report</title></head>
<body><h2>BER Report</h2>{html_body}</body></html>
"""
                    html_path.write_text(html, encoding="utf-8")
                    files_created = [html_path]
                    return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=files_created)
                except Exception as e:
                    # Fallback to DataFrame HTML if available
                    df = ber.df.copy()
                    if lines > 0:
                        df = df.head(lines)
                    df.to_html(str(html_path), index=False)
                    files_created = [html_path]
                    return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=files_created)
            elif fmt == "json":
                json_path = Path(output_file) if output_file else Path.cwd() / "ber.json"
                df = ber.df.copy()
                if check_anomalies:
                    # export anomalies when requested
                    from ..anomaly import merge_anomalies, get_high_ber_anomalies, get_unusual_ber_anomalies
                    anomalies = merge_anomalies(df, [get_high_ber_anomalies(df.copy()), get_unusual_ber_anomalies(df.copy())])
                    out_df = anomalies
                else:
                    out_df = df
                if lines > 0:
                    out_df = out_df.head(lines)
                out_df.to_json(str(json_path), orient="records")
                files_created = [json_path]
                return OperationResult(output_messages=[f"Saved JSON: {json_path}"], files_created=files_created)

            # Default to stdout
            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"BER execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_port(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute port operation."""
        try:
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []

            # Enrich with PM if available
            hca_m = HcaManager(ib_dir=dir_a, g=graph)
            ibpm = IbPm(ib_dir=dir_a)
            pminfo = PMInfo(ib_dir=dir_a, g=graph, hca_m=hca_m, ib_pm=ibpm)
            port = Port(ib_dir=dir_a, g=graph, pminfo=pminfo)

            # stdout rendering
            if kwargs.get("check_anomalies", False):
                # For --check, show pair-view and filter rows having non-zero link-down counters
                messages = port.print_pairs(num_lines=lines, sort=sort_column, hide_zero_linkdown=False, filter_nonzero_linkdown=True)
            else:
                df = port.df.copy()
                keep_cols = [c for c in (extended_columns or []) if c in df.columns.tolist()]
                base_cols = [c for c in Port.COLUMNS_TO_PRINT if c in df.columns.tolist()]
                columns = base_cols + keep_cols
                if abs(sort_column) > 0 and (abs(sort_column) - 1) < len(columns):
                    df = df.sort_values(by=columns[abs(sort_column) - 1], ascending=(sort_column < 0))
                df['Index'] = range(1, len(df) + 1)
                df = df[columns]
                if lines > 0:
                    df = df.head(lines)
                messages = [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                csv_path = Path(output_file) if output_file else Path.cwd() / "ports.csv"
                # For --check, export pair-view by default
                if kwargs.get("check_anomalies", False):
                    created = port.to_pairs_csv(csv_filename=str(csv_path), hide_zero_linkdown=False, filter_nonzero_linkdown=True)
                    return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=[csv_path])
                csv_cols = [c for c in Port.COLUMNS_TO_CSV if c in port.df.columns.tolist()] + keep_cols
                out_df = port.df[csv_cols].copy()
                out_df.to_csv(str(csv_path), index=False)
                return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=[csv_path])
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "ports.html"
                html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>Ports Report</title></head>
<body><h2>Ports Report</h2>{html_body}</body></html>
"""
                html_path.write_text(html, encoding="utf-8")
                return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=[html_path])
            elif fmt == "json":
                json_path = Path(output_file) if output_file else Path.cwd() / "ports.json"
                out_df = port.df.copy()
                if lines > 0:
                    out_df = out_df.head(lines)
                out_df.to_json(str(json_path), orient="records")
                return OperationResult(output_messages=[f"Saved JSON: {json_path}"], files_created=[json_path])

            # Pair-view stdout when --pairs requested via extend flag sentinel
            if ('pairs' in (extended_columns or [])):
                messages = port.print_pairs(num_lines=lines, sort=sort_column)
            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"PORT execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_pminfo(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute pminfo operation."""
        try:
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            overview: bool = kwargs.get("overview", False)
            plot: bool = kwargs.get("plot", False)

            hca_m = HcaManager(ib_dir=dir_a, g=graph)
            ibpm = IbPm(ib_dir=dir_a)
            pminfo = PMInfo(ib_dir=dir_a, g=graph, hca_m=hca_m, ib_pm=ibpm)

            if overview:
                messages = pminfo.print_overview(extended_columns=extended_columns)
            elif plot:
                messages = pminfo.print_plot(extended_columns=extended_columns)
            else:
                messages = pminfo.table(num_lines=lines, sort=sort_column, extended_columns=extended_columns)

            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                csv_path = Path(output_file) if output_file else Path.cwd() / "pminfo.csv"
                if check_anomalies:
                    df_anom = pminfo.get_anomalies() if hasattr(pminfo, 'get_anomalies') else pminfo.df.copy()
                    base_cols = [c for c in (PMInfo.COLUMNS_TO_PRINT if hasattr(PMInfo, 'COLUMNS_TO_PRINT') else []) if c in df_anom.columns]
                    keep_cols = [c for c in (extended_columns or []) if c in df_anom.columns]
                    columns = base_cols + keep_cols
                    df_out = df_anom.copy()
                    if 'Index' in base_cols and 'Index' not in df_out.columns:
                        df_out['Index'] = range(1, df_out.shape[0] + 1)
                    if columns:
                        df_out = df_out[columns]
                    df_out.to_csv(str(csv_path), index=False)
                    return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=[csv_path])
                created = pminfo.to_csv(csv_filename=str(csv_path), extended_columns=extended_columns)
                files_created = [Path(p) for p in created]
                return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=files_created)
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "pminfo.html"
                html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>PMInfo Report</title></head>
<body><h2>PMInfo Report</h2>{html_body}</body></html>
"""
                html_path.write_text(html, encoding="utf-8")
                return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=[html_path])
            elif fmt == "json":
                json_path = Path(output_file) if output_file else Path.cwd() / "pminfo.json"
                df = pminfo.df.copy()
                if lines > 0:
                    df = df.head(lines)
                df.to_json(str(json_path), orient="records")
                return OperationResult(output_messages=[f"Saved JSON: {json_path}"], files_created=[json_path])

            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"PMInfo execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_cc(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute cc operation."""
        try:
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            overview: bool = kwargs.get("overview", False)
            plot: bool = kwargs.get("plot", False)

            hca_m = HcaManager(ib_dir=dir_a, g=graph)
            xmit = Xmit(ib_dir=dir_a, g=graph, hca_m=hca_m)
            ibpm = IbPm(ib_dir=dir_a)
            pminfo = PMInfo(ib_dir=dir_a, g=graph, hca_m=hca_m, ib_pm=ibpm)
            cc = CongestionControl(ib_dir=dir_a, xmit=xmit, pminfo=pminfo)

            if overview:
                messages = cc.print_overview(extended_columns=extended_columns) if hasattr(cc, 'print_overview') else ["N/A"]
            elif plot:
                messages = cc.print_plot(extended_columns=extended_columns)
            else:
                messages = cc.table(num_lines=lines, sort=sort_column, extended_columns=extended_columns)

            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                csv_path = Path(output_file) if output_file else Path.cwd() / "cc.csv"
                if check_anomalies and hasattr(cc, 'get_anomalies'):
                    df_anom = cc.get_anomalies()
                    from ..cc import CongestionControl as CCClass
                    base_cols = [c for c in CCClass.COLUMNS_TO_PRINT_ANOMALY if c in df_anom.columns]
                    keep_cols = [c for c in (extended_columns or []) if c in df_anom.columns]
                    columns = base_cols + keep_cols
                    df_out = df_anom.copy()
                    if 'Index' in CCClass.COLUMNS_TO_PRINT_ANOMALY and 'Index' not in df_out.columns:
                        df_out['Index'] = range(1, df_out.shape[0] + 1)
                    if columns:
                        df_out = df_out[columns]
                    df_out.to_csv(str(csv_path), index=False)
                    return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=[csv_path])
                # default full CSV
                df = cc.df.copy() if hasattr(cc, 'df') else None
                if df is not None:
                    df.to_csv(str(csv_path), index=False)
                return OperationResult(output_messages=[f"Saved CSV: {csv_path}"], files_created=[csv_path])
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "cc.html"
                html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>CC Report</title></head>
<body><h2>CC Report</h2>{html_body}</body></html>
"""
                html_path.write_text(html, encoding="utf-8")
                return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=[html_path])
            elif fmt == "json":
                json_path = Path(output_file) if output_file else Path.cwd() / "cc.json"
                df = cc.df.copy() if hasattr(cc, 'df') else None
                if df is not None:
                    if lines > 0:
                        df = df.head(lines)
                    df.to_json(str(json_path), orient="records")
                return OperationResult(output_messages=[f"Saved JSON: {json_path}"], files_created=[json_path])

            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"CC execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_brief(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute brief operation."""
        try:
            from ..brief import Brief
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            tag: Optional[str] = kwargs.get("tag")

            # Build all managers
            hca_m = HcaManager(ib_dir=dir_a, g=graph)
            xmit = Xmit(ib_dir=dir_a, g=graph, hca_m=hca_m)
            port_m = Port(ib_dir=dir_a, g=graph)
            cable_m = CableManager(ib_dir=dir_a, g=graph, port_m=port_m, xmit_m=xmit)
            ber_m = Ber(ib_dir=dir_a, g=graph, use_net_dump_ext=True)
            ibpm = IbPm(ib_dir=dir_a)
            pminfo = PMInfo(ib_dir=dir_a, g=graph, hca_m=hca_m, ib_pm=ibpm)
            cc_m = CongestionControl(ib_dir=dir_a, xmit=xmit, pminfo=pminfo)
            hist_m = Histogram(ib_dir=dir_a, g=graph, xmit=xmit)

            brief = Brief(graph, xmit, hca_m, cable_m, ber_m, cc_m, hist_m, dir_a, tag)
            messages = brief.table(sort=sort_column, num_lines=lines, extended_columns=extended_columns)

            fmt = (output_format or "stdout").lower()
            if fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "brief.html"
                html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>Brief Report</title></head>
<body><h2>Brief Report</h2>{html_body}</body></html>
"""
                html_path.write_text(html, encoding="utf-8")
                return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=[html_path])

            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"BRIEF execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_nlastic(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute nlastic operation."""
        # TODO: Implement nlastic operation (same as brief)
        return self._execute_brief(parsed_data, **kwargs)
    
    def _execute_histogram(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute histogram operation."""
        try:
            dir_a: str = parsed_data.get("dir_a", "")
            graph: Graph = parsed_data.get("graph")
            if not graph:
                raise OperationError("Graph is not initialized")

            output_format: str = kwargs.get("output_format", "stdout")
            output_file: Optional[Path] = kwargs.get("output_file")
            lines: int = kwargs.get("lines", 50)
            sort_column: int = kwargs.get("sort_column", 0)
            extended_columns: List[str] = kwargs.get("extended_columns", []) or []
            overview: bool = kwargs.get("overview", False)
            plot: bool = kwargs.get("plot", False)

            hca_m = HcaManager(ib_dir=dir_a, g=graph)
            xmit = Xmit(ib_dir=dir_a, g=graph, hca_m=hca_m)
            hist = Histogram(ib_dir=dir_a, g=graph, xmit=xmit)

            if overview:
                messages = hist.print_overview(extended_columns=extended_columns)
            elif plot:
                messages = hist.print_plot(extended_columns=extended_columns)
            else:
                messages = hist.table(num_lines=lines, sort=sort_column, extended_columns=extended_columns)

            fmt = (output_format or "stdout").lower()
            if fmt == "csv":
                csv_path = Path(output_file) if output_file else Path.cwd() / "histogram.csv"
                created = hist.to_csv(csv_filename=str(csv_path), extended_columns=extended_columns)
                return OperationResult(output_messages=[f"Saved CSV: {', '.join(created)}"], files_created=[Path(p) for p in created])
            elif fmt == "html":
                html_path = Path(output_file) if output_file else Path.cwd() / "histogram.html"
                html_body = "<br/>".join(f"<pre>{m}</pre>" for m in messages)
                html = f"""
<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><title>Histogram Report</title></head>
<body><h2>Histogram Report</h2>{html_body}</body></html>
"""
                html_path.write_text(html, encoding="utf-8")
                return OperationResult(output_messages=[f"Saved HTML: {html_path}"], files_created=[html_path])
            elif fmt == "json":
                json_path = Path(output_file) if output_file else Path.cwd() / "histogram.json"
                df = hist.df.copy()
                if lines > 0:
                    df = df.head(lines)
                df.to_json(str(json_path), orient="records")
                return OperationResult(output_messages=[f"Saved JSON: {json_path}"], files_created=[json_path])

            return OperationResult(output_messages=messages)

        except Exception as e:
            logger.error(f"HISTOGRAM execution failed: {e}")
            return OperationResult(exit_code=1, output_messages=[f"Error: {e}"], error_message=str(e))
    
    def _execute_tableau(self, parsed_data: Dict[str, Any], **kwargs: Any) -> OperationResult:
        """Execute tableau operation."""
        # TODO: Implement tableau operation
        return OperationResult(
            output_messages=["Tableau operation executed (placeholder)"]
        )
