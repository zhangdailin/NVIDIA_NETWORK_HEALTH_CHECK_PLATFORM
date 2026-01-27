"""
UFM CSV Analysis Service

Analyzes UFM CSV files exported from NVIDIA UFM REST API.
Provides comprehensive analysis of network performance metrics including:
- BER (Bit Error Rate) analysis
- Link status and errors
- Temperature monitoring
- Cable information
- Port performance counters
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def safe_float(value):
    """Convert value to float, replacing NaN/inf with None for JSON compatibility."""
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def safe_to_dict(df):
    """Convert DataFrame to dict, replacing NaN/inf with None for JSON compatibility."""
    # Replace NaN and inf with None before converting to dict
    df_clean = df.replace([np.nan, np.inf, -np.inf], None)
    return df_clean.to_dict('records')


class UFMCSVService:
    """Service for analyzing UFM CSV data."""

    def __init__(self):
        """Initialize UFM CSV service."""
        self.df: Optional[pd.DataFrame] = None
        self.file_path: Optional[Path] = None

    def load_csv(self, file_path: Path, encoding: str = 'ascii') -> Dict[str, Any]:
        """
        Load and validate UFM CSV file.

        Args:
            file_path: Path to CSV file
            encoding: File encoding (default: ascii)

        Returns:
            Dictionary with load status and basic statistics
        """
        try:
            self.file_path = file_path
            self.df = pd.read_csv(file_path, encoding=encoding, encoding_errors='replace')

            logger.info(f"Loaded UFM CSV: {len(self.df)} rows, {len(self.df.columns)} columns")

            return {
                "status": "success",
                "rows": len(self.df),
                "columns": len(self.df.columns),
                "unique_nodes": int(self.df['Node_GUID'].nunique()),
                "unique_hosts": int(self.df['host_name'].nunique()),
            }
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            raise

    def analyze_ber(self) -> Dict[str, Any]:
        """
        Analyze Bit Error Rate (BER) metrics.

        Returns:
            Dictionary with BER analysis results
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        # BER columns
        ber_cols = {
            'Total_Raw_BER': 'Raw BER',
            'Effective_BER': 'Effective BER',
            'Symbol_BER': 'Symbol BER',
        }

        results = {
            "summary": {},
            "critical_ports": [],
            "warning_ports": [],
        }

        # Analyze each BER type
        for col, label in ber_cols.items():
            if col in self.df.columns:
                ber_data = pd.to_numeric(self.df[col], errors='coerce')
                non_zero = (ber_data > 0).sum()

                results["summary"][label] = {
                    "ports_with_errors": int(non_zero),
                    "max_value": safe_float(ber_data.max()) if non_zero > 0 else 0,
                    "avg_value": safe_float(ber_data[ber_data > 0].mean()) if non_zero > 0 else 0,
                }

        # Find critical ports (BER > 1e-6)
        if 'Symbol_BER' in self.df.columns:
            symbol_ber = pd.to_numeric(self.df['Symbol_BER'], errors='coerce')
            critical_mask = symbol_ber > 1e-6

            if critical_mask.any():
                critical_df = self.df[critical_mask].copy()
                results["critical_ports"] = safe_to_dict(critical_df[[
                    'Node_GUID', 'Port_Number', 'node_description',
                    'Symbol_BER', 'Symbol_Errors', 'host_name'
                ]].head(100))

        # Find warning ports (BER > 1e-9)
        if 'Symbol_BER' in self.df.columns:
            warning_mask = (symbol_ber > 1e-9) & (symbol_ber <= 1e-6)

            if warning_mask.any():
                warning_df = self.df[warning_mask].copy()
                results["warning_ports"] = safe_to_dict(warning_df[[
                    'Node_GUID', 'Port_Number', 'node_description',
                    'Symbol_BER', 'Symbol_Errors', 'host_name'
                ]].head(100))

        return results

    def analyze_link_status(self) -> Dict[str, Any]:
        """
        Analyze link status and errors.

        Returns:
            Dictionary with link status analysis
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        results = {
            "summary": {},
            "down_links": [],
            "error_recovery": [],
        }

        # Link down analysis
        if 'Link_Down' in self.df.columns:
            link_down = pd.to_numeric(self.df['Link_Down'], errors='coerce')
            down_count = (link_down > 0).sum()

            results["summary"]["links_down"] = int(down_count)

            if down_count > 0:
                down_df = self.df[link_down > 0].copy()
                results["down_links"] = safe_to_dict(down_df[[
                    'Node_GUID', 'Port_Number', 'node_description',
                    'Link_Down', 'Status_Message', 'host_name'
                ]].head(100))

        # Error recovery analysis
        if 'LinkErrorRecoveryCounter' in self.df.columns:
            error_recovery = pd.to_numeric(self.df['LinkErrorRecoveryCounter'], errors='coerce')
            recovery_count = (error_recovery > 0).sum()

            results["summary"]["error_recovery_events"] = int(recovery_count)

            if recovery_count > 0:
                recovery_df = self.df[error_recovery > 0].copy()
                results["error_recovery"] = safe_to_dict(recovery_df[[
                    'Node_GUID', 'Port_Number', 'node_description',
                    'LinkErrorRecoveryCounter', 'host_name'
                ]].head(100))

        return results

    def analyze_temperature(self) -> Dict[str, Any]:
        """
        Analyze temperature metrics.

        Returns:
            Dictionary with temperature analysis
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        results = {
            "summary": {},
            "hot_ports": [],
        }

        if 'Temperature' in self.df.columns:
            temp_data = pd.to_numeric(self.df['Temperature'], errors='coerce').dropna()

            if len(temp_data) > 0:
                results["summary"] = {
                    "avg_temp": safe_float(temp_data.mean()),
                    "max_temp": safe_float(temp_data.max()),
                    "min_temp": safe_float(temp_data.min()),
                    "ports_monitored": int(len(temp_data)),
                }

                # Find hot ports (> 60°C)
                hot_mask = self.df['Temperature'] > 60
                if hot_mask.any():
                    hot_df = self.df[hot_mask].copy()
                    results["hot_ports"] = safe_to_dict(hot_df[[
                        'Node_GUID', 'Port_Number', 'node_description',
                        'Temperature', 'Module_Temperature', 'host_name'
                    ]].head(100))

        return results

    def analyze_cables(self) -> Dict[str, Any]:
        """
        Analyze cable information.

        Returns:
            Dictionary with cable analysis
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        results = {
            "summary": {},
            "cable_types": [],
            "cable_lengths": [],
        }

        if 'Cable_PN' in self.df.columns:
            cables_with_pn = self.df['Cable_PN'].notna().sum()
            results["summary"]["cables_identified"] = int(cables_with_pn)

            # Cable types
            if 'Cable_Type' in self.df.columns:
                cable_types = self.df['Cable_Type'].value_counts().head(10)
                results["cable_types"] = [
                    {"type": str(k), "count": int(v)}
                    for k, v in cable_types.items()
                ]

            # Cable lengths
            if 'Cable_Length' in self.df.columns:
                cable_lengths = self.df['Cable_Length'].value_counts().head(10)
                results["cable_lengths"] = [
                    {"length": str(k), "count": int(v)}
                    for k, v in cable_lengths.items()
                ]

        return results

    def analyze_port_errors(self) -> Dict[str, Any]:
        """
        Analyze port error counters.

        Returns:
            Dictionary with port error analysis
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        error_cols = {
            'PortRcvErrors': 'Receive Errors',
            'PortXmitDiscards': 'Transmit Discards',
            'PortRcvRemotePhysicalErrors': 'Remote Physical Errors',
            'LinkIntegrityErrors': 'Link Integrity Errors',
        }

        results = {
            "summary": {},
            "error_ports": [],
        }

        # Analyze each error type
        for col, label in error_cols.items():
            if col in self.df.columns:
                error_data = pd.to_numeric(self.df[col], errors='coerce')
                non_zero = (error_data > 0).sum()

                results["summary"][label] = {
                    "ports_with_errors": int(non_zero),
                    "total_errors": int(error_data.sum()),
                    "max_errors": int(error_data.max()) if non_zero > 0 else 0,
                }

        # Find ports with multiple error types
        error_count = pd.DataFrame()
        for col in error_cols.keys():
            if col in self.df.columns:
                error_count[col] = pd.to_numeric(self.df[col], errors='coerce') > 0

        if not error_count.empty:
            multi_error_mask = error_count.sum(axis=1) > 1
            if multi_error_mask.any():
                error_df = self.df[multi_error_mask].copy()
                results["error_ports"] = safe_to_dict(error_df[[
                    'Node_GUID', 'Port_Number', 'node_description',
                    'PortRcvErrors', 'PortXmitDiscards', 'host_name'
                ]].head(100))

        return results

    def analyze_performance(self) -> Dict[str, Any]:
        """
        Analyze port performance metrics (bandwidth, traffic, etc.).

        Returns:
            Dictionary with performance analysis
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        results = {
            "summary": {},
            "traffic_stats": {},
            "top_bandwidth_ports": [],
            "congestion_ports": [],
        }

        # Traffic analysis
        traffic_cols = {
            'PortXmitData': 'Transmit Data',
            'PortRcvData': 'Receive Data',
            'PortXmitPkts': 'Transmit Packets',
            'PortRcvPkts': 'Receive Packets',
        }

        for col, label in traffic_cols.items():
            if col in self.df.columns:
                data = pd.to_numeric(self.df[col], errors='coerce')
                results["traffic_stats"][label] = {
                    "total": int(data.sum()),
                    "average": safe_float(data.mean()),
                    "max": safe_float(data.max()),
                    "p95": safe_float(data.quantile(0.95)),
                    "p99": safe_float(data.quantile(0.99)),
                }

        # Find top bandwidth ports
        if 'PortXmitData' in self.df.columns and 'PortRcvData' in self.df.columns:
            xmit = pd.to_numeric(self.df['PortXmitData'], errors='coerce').fillna(0)
            rcv = pd.to_numeric(self.df['PortRcvData'], errors='coerce').fillna(0)
            total_traffic = xmit + rcv

            top_indices = total_traffic.nlargest(20).index
            if len(top_indices) > 0:
                top_df = self.df.loc[top_indices].copy()
                top_df['Total_Traffic'] = total_traffic.loc[top_indices]
                results["top_bandwidth_ports"] = safe_to_dict(top_df[[
                    'Node_GUID', 'Port_Number', 'node_description',
                    'PortXmitData', 'PortRcvData', 'Total_Traffic', 'host_name'
                ]].head(20))

        # Congestion analysis
        if 'PortXmitWait' in self.df.columns:
            xmit_wait = pd.to_numeric(self.df['PortXmitWait'], errors='coerce')
            congestion_mask = xmit_wait > 1000  # Threshold for congestion

            if congestion_mask.any():
                congestion_df = self.df[congestion_mask].copy()
                results["congestion_ports"] = safe_to_dict(congestion_df[[
                    'Node_GUID', 'Port_Number', 'node_description',
                    'PortXmitWait', 'PortXmitData', 'host_name'
                ]].head(50))

                results["summary"]["congested_ports"] = int(congestion_mask.sum())

        return results

    def analyze_port_distribution(self) -> Dict[str, Any]:
        """
        Analyze port speed, width, and type distribution.

        Returns:
            Dictionary with port distribution analysis
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        results = {
            "speed_distribution": [],
            "width_distribution": [],
            "state_distribution": [],
        }

        # Speed distribution
        if 'Port_Speed' in self.df.columns:
            speeds = self.df['Port_Speed'].value_counts()
            results["speed_distribution"] = [
                {"speed": str(k), "count": int(v), "percentage": round(v / len(self.df) * 100, 2)}
                for k, v in speeds.items()
            ]

        # Width distribution
        if 'Port_Width' in self.df.columns:
            widths = self.df['Port_Width'].value_counts()
            results["width_distribution"] = [
                {"width": str(k), "count": int(v), "percentage": round(v / len(self.df) * 100, 2)}
                for k, v in widths.items()
            ]

        # State distribution
        if 'Port_State' in self.df.columns:
            states = self.df['Port_State'].value_counts()
            results["state_distribution"] = [
                {"state": str(k), "count": int(v), "percentage": round(v / len(self.df) * 100, 2)}
                for k, v in states.items()
            ]

        return results

    def calculate_health_score(self) -> Dict[str, Any]:
        """
        Calculate overall network health score (0-100) with robust error handling.

        Returns:
            Dictionary with health score and breakdown
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        try:
            scores = {}
            weights = {}

            # BER Health (25%)
            if 'Symbol_BER' in self.df.columns:
                try:
                    symbol_ber = pd.to_numeric(self.df['Symbol_BER'], errors='coerce')
                    critical_ber = (symbol_ber > 1e-6).sum()
                    warning_ber = ((symbol_ber > 1e-9) & (symbol_ber <= 1e-6)).sum()
                    total_ports = len(self.df)

                    ber_score = 100
                    if critical_ber > 0:
                        ber_score -= (critical_ber / total_ports) * 50
                    if warning_ber > 0:
                        ber_score -= (warning_ber / total_ports) * 25

                    scores['ber_health'] = max(0, ber_score)
                    weights['ber_health'] = 0.25
                except Exception as e:
                    logger.warning(f"BER health calculation failed: {e}")

            # Link Health (25%)
            try:
                link_score = 100
                if 'Link_Down' in self.df.columns:
                    link_down = pd.to_numeric(self.df['Link_Down'], errors='coerce')
                    down_count = (link_down > 0).sum()
                    if down_count > 0:
                        link_score -= (down_count / len(self.df)) * 50

                if 'LinkErrorRecoveryCounter' in self.df.columns:
                    error_recovery = pd.to_numeric(self.df['LinkErrorRecoveryCounter'], errors='coerce')
                    recovery_count = (error_recovery > 0).sum()
                    if recovery_count > 0:
                        link_score -= (recovery_count / len(self.df)) * 25

                scores['link_health'] = max(0, link_score)
                weights['link_health'] = 0.25
            except Exception as e:
                logger.warning(f"Link health calculation failed: {e}")

            # Temperature Health (20%)
            try:
                temp_score = 100
                if 'Temperature' in self.df.columns:
                    temp_data = pd.to_numeric(self.df['Temperature'], errors='coerce').dropna()
                    if len(temp_data) > 0:
                        hot_ports = (temp_data > 60).sum()
                        warm_ports = ((temp_data > 50) & (temp_data <= 60)).sum()

                        if hot_ports > 0:
                            temp_score -= (hot_ports / len(temp_data)) * 40
                        if warm_ports > 0:
                            temp_score -= (warm_ports / len(temp_data)) * 20

                scores['temperature_health'] = max(0, temp_score)
                weights['temperature_health'] = 0.20
            except Exception as e:
                logger.warning(f"Temperature health calculation failed: {e}")

            # Error Health (30%)
            try:
                error_score = 100
                error_cols = ['PortRcvErrors', 'PortXmitDiscards', 'PortRcvRemotePhysicalErrors']

                error_count = 0
                for col in error_cols:
                    if col in self.df.columns:
                        errors = pd.to_numeric(self.df[col], errors='coerce')
                        error_count += (errors > 0).sum()

                if error_count > 0:
                    error_score -= min(50, (error_count / len(self.df)) * 30)

                scores['error_health'] = max(0, error_score)
                weights['error_health'] = 0.30
            except Exception as e:
                logger.warning(f"Error health calculation failed: {e}")

            # If no scores were calculated, return default
            if not scores:
                logger.warning("No health metrics could be calculated - insufficient data columns")
                return {
                    "overall_score": 0,
                    "scores": {},
                    "grade": "N/A",
                    "status": "Insufficient Data",
                }

            # Calculate weighted average
            total_weight = sum(weights.values())
            overall_score = sum(scores[k] * weights[k] for k in scores.keys()) / total_weight if total_weight > 0 else 0

            return {
                "overall_score": round(overall_score, 1),
                "scores": {k: round(v, 1) for k, v in scores.items()},
                "grade": self._get_health_grade(overall_score),
                "status": self._get_health_status(overall_score),
            }
        except Exception as e:
            logger.error(f"Health score calculation failed: {e}")
            # Return safe default instead of raising
            return {
                "overall_score": 0,
                "scores": {},
                "grade": "N/A",
                "status": "Calculation Failed",
            }

    def _get_health_grade(self, score: float) -> str:
        """Convert health score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def _get_health_status(self, score: float) -> str:
        """Get health status description."""
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Fair"
        elif score >= 60:
            return "Poor"
        else:
            return "Critical"

    def get_full_analysis(self) -> Dict[str, Any]:
        """
        Perform complete UFM CSV analysis with robust error handling.

        Returns:
            Dictionary with all analysis results
        """
        if self.df is None:
            raise ValueError("No CSV data loaded")

        logger.info("Starting full UFM CSV analysis...")

        results = {}

        # Health Score - with fallback
        try:
            results["health_score"] = self.calculate_health_score()
            logger.info("Health score calculation completed")
        except Exception as e:
            logger.error(f"Health score calculation failed: {e}")
            results["health_score"] = {
                "overall_score": 0,
                "scores": {},
                "grade": "N/A",
                "status": "Error"
            }

        # BER Analysis - with fallback
        try:
            results["ber_analysis"] = self.analyze_ber()
            logger.info("BER analysis completed")
        except Exception as e:
            logger.error(f"BER analysis failed: {e}")
            results["ber_analysis"] = {"summary": {}, "critical_ports": [], "warning_ports": []}

        # Link Status - with fallback
        try:
            results["link_status"] = self.analyze_link_status()
            logger.info("Link status analysis completed")
        except Exception as e:
            logger.error(f"Link status analysis failed: {e}")
            results["link_status"] = {"summary": {}, "down_links": [], "error_recovery": []}

        # Temperature - with fallback
        try:
            results["temperature"] = self.analyze_temperature()
            logger.info("Temperature analysis completed")
        except Exception as e:
            logger.error(f"Temperature analysis failed: {e}")
            results["temperature"] = {"summary": {}, "hot_ports": []}

        # Cables - with fallback
        try:
            results["cables"] = self.analyze_cables()
            logger.info("Cable analysis completed")
        except Exception as e:
            logger.error(f"Cable analysis failed: {e}")
            results["cables"] = {"summary": {}, "cable_types": [], "cable_lengths": []}

        # Port Errors - with fallback
        try:
            results["port_errors"] = self.analyze_port_errors()
            logger.info("Port errors analysis completed")
        except Exception as e:
            logger.error(f"Port errors analysis failed: {e}")
            results["port_errors"] = {"summary": {}, "error_ports": []}

        # Performance - with fallback
        try:
            results["performance"] = self.analyze_performance()
            logger.info("Performance analysis completed")
        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
            results["performance"] = {
                "summary": {},
                "traffic_stats": {},
                "top_bandwidth_ports": [],
                "congestion_ports": []
            }

        # Port Distribution - with fallback
        try:
            results["port_distribution"] = self.analyze_port_distribution()
            logger.info("Port distribution analysis completed")
        except Exception as e:
            logger.error(f"Port distribution analysis failed: {e}")
            results["port_distribution"] = {
                "speed_distribution": [],
                "width_distribution": [],
                "state_distribution": []
            }

        logger.info("Full UFM CSV analysis completed successfully")
        return results
