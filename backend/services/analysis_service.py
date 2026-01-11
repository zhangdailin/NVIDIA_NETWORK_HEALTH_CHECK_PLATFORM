"""Core analysis service that will replace direct ib_analysis usage."""

from __future__ import annotations

import asyncio
import datetime
import logging
import math
import numbers
from concurrent.futures import ThreadPoolExecutor
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .health_score import calculate_health_score, health_report_to_dict

import pandas as pd

from .anomalies import (
    IBH_ANOMALY_AGG_COL,
    IBH_ANOMALY_AGG_WEIGHT,
    IBH_ANOMALY_TBL_KEY,
    AnomlyType,
)
from .ar_info_service import ArInfoService
from .ber_service import BerService
from .brief_service import BriefService
from .buffer_histogram_service import BufferHistogramService
from .cable_service import CableService
from .credit_watchdog_service import CreditWatchdogService
from .extended_node_info_service import ExtendedNodeInfoService
from .extended_port_info_service import ExtendedPortInfoService
from .extended_switch_info_service import ExtendedSwitchInfoService
from .fan_service import FanService
from .fec_mode_service import FecModeService
from .hca_service import HcaService
from .histogram_service import HistogramService
from .ibdiagnet import read_index_table, read_table
from .link_oscillation_service import LinkOscillationService
from .mlnx_counters_service import MlnxCountersService
from .n2n_security_service import N2NSecurityService
from .neighbors_service import NeighborsService
from .pci_performance_service import PciPerformanceService
from .per_lane_performance_service import PerLanePerformanceService
from .phy_diagnostics_service import PhyDiagnosticsService
from .pkey_service import PkeyService
from .pm_delta_service import PmDeltaService
from .port_hierarchy_service import PortHierarchyService
from .power_sensors_service import PowerSensorsService
from .qos_service import QosService
from .routing_config_service import RoutingConfigService
from .routing_service import RoutingService
from .sharp_service import SharpService
from .sm_info_service import SMInfoService
from .switch_service import SwitchService
from .system_info_service import SystemInfoService
from .temp_alerts_service import TempAlertsService
from .vports_service import VPortsService
from .warnings_service import WarningsService
from .xmit_service import XmitService

logger = logging.getLogger(__name__)

MAX_PREVIEW_ROWS: Optional[int] = None

@dataclass
class IbdiagnetDataset:
    """
    Thin wrapper around an extracted ibdiagnet directory.

    It loads index metadata lazily so later stages (brief/cable/xmit/etc.)
    can fetch the DataFrames they need without touching ib_analysis modules.
    """

    root: Path
    _index_cache: Optional[pd.DataFrame] = None

    @property
    def index_table(self) -> pd.DataFrame:
        if self._index_cache is None:
            db_csv = self._find_db_csv()
            self._index_cache = read_index_table(db_csv)
        return self._index_cache

    def table(self, name: str) -> pd.DataFrame:
        db_csv = self._find_db_csv()
        return read_table(db_csv, name, self.index_table)

    def _find_db_csv(self) -> Path:
        matches = sorted(self.root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.root}")
        return matches[0]


class AnalysisService:
    """
    Entry point for orchestrating ibdiagnet-based health checks.

    For now it only loads the dataset; subsequent changes will extend it
    to run the equivalent of brief/cable/xmit/ber/hca processing.
    """

    def __init__(self, *, expected_topology_path: Optional[Path] = None):
        self._dataset_cache: Dict[Path, IbdiagnetDataset] = {}
        self._cache_lock = threading.Lock()  # Thread-safe cache access
        self._service_result_cache: Dict[Tuple[str, Path], object] = {}
        self._service_cache_lock = threading.Lock()
        path = (
            Path(expected_topology_path).expanduser()
            if expected_topology_path
            else self._default_expected_topology_path()
        )
        self._expected_topology_path = path if path and path.exists() else None

    def load_dataset(self, extracted_dir: Path) -> IbdiagnetDataset:
        extracted_dir = extracted_dir.resolve()

        # Thread-safe cache access
        with self._cache_lock:
            dataset = self._dataset_cache.get(extracted_dir)
            if dataset is None:
                dataset = IbdiagnetDataset(root=extracted_dir)
                self._dataset_cache[extracted_dir] = dataset
        return dataset

    def release_dataset(self, extracted_dir: Path) -> None:
        """Release cached dataset/service state once analysis completes."""
        normalized = self._normalize_dataset_path(extracted_dir)
        with self._cache_lock:
            self._dataset_cache.pop(normalized, None)
        self.clear_cached_service(dataset_path=normalized)

    def _normalize_dataset_path(self, dataset_path: Path) -> Path:
        try:
            return dataset_path.resolve()
        except Exception:
            return dataset_path

    def _get_cached_service_result(self, key: str, dataset_path: Path):
        normalized = self._normalize_dataset_path(dataset_path)
        with self._service_cache_lock:
            return self._service_result_cache.get((key, normalized))

    def _set_cached_service_result(self, key: str, dataset_path: Path, value: object) -> None:
        normalized = self._normalize_dataset_path(dataset_path)
        with self._service_cache_lock:
            self._service_result_cache[(key, normalized)] = value

    def clear_cached_service(self, dataset_path: Optional[Path] = None, service_key: Optional[str] = None) -> None:
        """Clear cached service results to avoid stale data / free memory."""
        with self._service_cache_lock:
            if dataset_path is None and service_key is None:
                self._service_result_cache.clear()
                return
            normalized = self._normalize_dataset_path(dataset_path) if dataset_path else None
            keys_to_remove = []
            for (key, path_key) in list(self._service_result_cache.keys()):
                if service_key and key != service_key:
                    continue
                if normalized and path_key != normalized:
                    continue
                keys_to_remove.append((key, path_key))
            for cache_key in keys_to_remove:
                self._service_result_cache.pop(cache_key, None)

    def _default_expected_topology_path(self) -> Optional[Path]:
        env_var = os.environ.get("EXPECTED_TOPOLOGY_FILE")
        if env_var:
            candidate = Path(env_var).expanduser()
            if candidate.exists():
                return candidate
        default = Path("config/expected_topology.json")
        if default.exists():
            return default
        return None

    async def analyze_ibdiagnet(
        self,
        *,
        target_dir: Path,
        task_dir: Path,
        task_id: str,
        executor: ThreadPoolExecutor,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> Dict[str, object]:
        """
        Execute the pipeline and return all artifacts required by the frontend.
        """
        dataset = self.load_dataset(target_dir)
        target_dir = dataset.root
        loop = loop or asyncio.get_event_loop()

        try:
            service_specs = [
                ("cable", "Running native cable analysis...", self._run_cable_service),
                ("xmit", "Running native xmit analysis...", self._run_xmit_service),
                ("link_oscillation", "Running link oscillation analysis...", self._run_link_oscillation_service),
                ("ber", "Running native BER analysis...", self._run_ber_service),
                ("hca", "Running native HCA analysis...", self._run_hca_service),
                ("fan", "Running native fan analysis...", self._run_fan_service),
                ("histogram", "Running performance histogram analysis...", self._run_histogram_service),
                ("warnings", "Running ibdiagnet warnings analysis...", self._run_warnings_service),
                ("switch", "Running switch analysis...", self._run_switch_service),
                ("routing", "Running routing analysis...", self._run_routing_service),
                ("qos", "Running QoS/VL arbitration analysis...", self._run_qos_service),
                ("sm_info", "Running Subnet Manager analysis...", self._run_sm_info_service),
                ("port_hierarchy", "Running Port Hierarchy analysis...", self._run_port_hierarchy_service),
                ("mlnx_counters", "Running MLNX Counters analysis...", self._run_mlnx_counters_service),
                ("pm_delta", "Running PM Delta analysis...", self._run_pm_delta_service),
                ("vports", "Running VPorts analysis...", self._run_vports_service),
                ("pkey", "Running PKEY analysis...", self._run_pkey_service),
                ("system_info", "Running System Info analysis...", self._run_system_info_service),
                ("extended_port_info", "Running Extended Port Info analysis...", self._run_extended_port_info_service),
                ("ar_info", "Running AR Info analysis...", self._run_ar_info_service),
                ("sharp", "Running SHARP analysis...", self._run_sharp_service),
                ("fec_mode", "Running FEC Mode analysis...", self._run_fec_mode_service),
                ("phy_diagnostics", "Running PHY Diagnostics analysis...", self._run_phy_diagnostics_service),
                ("neighbors", "Running Neighbors analysis...", self._run_neighbors_service),
                ("buffer_histogram", "Running Buffer Histogram analysis...", self._run_buffer_histogram_service),
                ("extended_node_info", "Running Extended Node Info analysis...", self._run_extended_node_info_service),
                ("extended_switch_info", "Running Extended Switch Info analysis...", self._run_extended_switch_info_service),
                ("power_sensors", "Running Power Sensors analysis...", self._run_power_sensors_service),
                ("routing_config", "Running Routing Config analysis...", self._run_routing_config_service),
                ("temp_alerts", "Running Temperature Alerts analysis...", self._run_temp_alerts_service),
                ("credit_watchdog", "Running Credit Watchdog analysis...", self._run_credit_watchdog_service),
                ("pci_performance", "Running PCI Performance analysis...", self._run_pci_performance_service),
                ("per_lane_performance", "Running Per-Lane Performance analysis...", self._run_per_lane_performance_service),
                ("n2n_security", "Running N2N Security analysis...", self._run_n2n_security_service),
            ]

            service_futures = {}
            for name, log_message, runner in service_specs:
                logger.info(log_message)
                service_futures[name] = loop.run_in_executor(executor, runner, target_dir)

            results = await asyncio.gather(*service_futures.values())

            service_results = {
                name: result for (name, _, _), result in zip(service_specs, results)
            }

            logger.info("All analyses completed")

            cable_analysis = service_results["cable"]
            xmit_analysis = service_results["xmit"]
            link_oscillation_analysis = service_results["link_oscillation"]
            ber_analysis = service_results["ber"]
            hca_data, hca_anomaly_df = service_results["hca"]
            fan_analysis = service_results["fan"]
            histogram_analysis = service_results["histogram"]
            warnings_analysis = service_results["warnings"]
            switch_analysis = service_results["switch"]
            routing_analysis = service_results["routing"]
            qos_analysis = service_results["qos"]
            sm_info_analysis = service_results["sm_info"]
            port_hierarchy_analysis = service_results["port_hierarchy"]
            mlnx_counters_analysis = service_results["mlnx_counters"]
            pm_delta_analysis = service_results["pm_delta"]
            vports_analysis = service_results["vports"]
            pkey_analysis = service_results["pkey"]
            system_info_analysis = service_results["system_info"]
            extended_port_info_analysis = service_results["extended_port_info"]
            ar_info_analysis = service_results["ar_info"]
            sharp_analysis = service_results["sharp"]
            fec_mode_analysis = service_results["fec_mode"]
            phy_diagnostics_analysis = service_results["phy_diagnostics"]
            neighbors_analysis = service_results["neighbors"]
            buffer_histogram_analysis = service_results["buffer_histogram"]
            extended_node_info_analysis = service_results["extended_node_info"]
            extended_switch_info_analysis = service_results["extended_switch_info"]
            power_sensors_analysis = service_results["power_sensors"]
            routing_config_analysis = service_results["routing_config"]
            temp_alerts_analysis = service_results["temp_alerts"]
            credit_watchdog_analysis = service_results["credit_watchdog"]
            pci_performance_analysis = service_results["pci_performance"]
            per_lane_performance_analysis = service_results["per_lane_performance"]
            n2n_security_analysis = service_results["n2n_security"]
        finally:
            self.release_dataset(target_dir)

        cable_rows = cable_analysis.data
        cable_summary = cable_analysis.summary or {}
        xmit_rows = xmit_analysis.data
        link_oscillation_rows = link_oscillation_analysis.data
        ber_rows = ber_analysis.data
        hca_rows = hca_data
        fan_rows = fan_analysis.data
        histogram_rows = histogram_analysis.data
        switch_rows = switch_analysis.data
        routing_rows = routing_analysis.data
        qos_rows = qos_analysis.data
        sm_info_rows = sm_info_analysis.data
        port_hierarchy_rows = port_hierarchy_analysis.data
        mlnx_counters_rows = mlnx_counters_analysis.data
        pm_delta_rows = pm_delta_analysis.data
        vports_rows = vports_analysis.data
        pkey_rows = pkey_analysis.data
        system_info_rows = system_info_analysis.data
        extended_port_info_rows = extended_port_info_analysis.data
        ar_info_rows = ar_info_analysis.data
        sharp_rows = sharp_analysis.data
        fec_mode_rows = fec_mode_analysis.data
        phy_diagnostics_rows = phy_diagnostics_analysis.data
        neighbors_rows = neighbors_analysis.data
        buffer_histogram_rows = buffer_histogram_analysis.data
        extended_node_info_rows = extended_node_info_analysis.data
        extended_switch_info_rows = extended_switch_info_analysis.data
        power_sensors_rows = power_sensors_analysis.data
        routing_config_rows = routing_config_analysis.data
        temp_alerts_rows = temp_alerts_analysis.data
        credit_watchdog_rows = credit_watchdog_analysis.data
        pci_performance_rows = pci_performance_analysis.data
        per_lane_performance_rows = per_lane_performance_analysis.data
        n2n_security_rows = n2n_security_analysis.data
        cable_anomalies = self._flatten_anomaly_records(cable_analysis.anomalies)
        xmit_anomalies = self._flatten_anomaly_records(xmit_analysis.anomalies)
        ber_anomalies = self._flatten_anomaly_records(ber_analysis.anomalies)
        hca_anomalies = self._flatten_anomaly_records(hca_anomaly_df)
        fan_anomalies = self._flatten_anomaly_records(fan_analysis.anomalies)
        histogram_anomalies = self._flatten_anomaly_records(histogram_analysis.anomalies)
        routing_anomalies = self._flatten_anomaly_records(routing_analysis.anomalies)
        pci_performance_anomalies = self._flatten_anomaly_records(pci_performance_analysis.anomalies)
        qos_anomalies = self._flatten_anomaly_records(qos_analysis.anomalies)
        mlnx_counters_anomalies = self._flatten_anomaly_records(mlnx_counters_analysis.anomalies)
        pm_delta_anomalies = self._flatten_anomaly_records(pm_delta_analysis.anomalies)

        logger.info("Building analysis brief locally...")
        brief_payload = await loop.run_in_executor(
            executor,
            self._build_brief,
            xmit_rows,
            cable_rows,
            ber_rows,
            hca_rows,
        )
        analysis_rows = brief_payload["data"]
        extra_sources = [
            ("cable", cable_anomalies),
            ("xmit", xmit_anomalies),
            ("ber", ber_anomalies),
            ("hca", hca_anomalies),
            ("fan", fan_anomalies),
            ("histogram", histogram_anomalies),
            ("routing", routing_anomalies),
            ("qos", qos_anomalies),
            ("mlnx_counters", mlnx_counters_anomalies),
            ("pm_delta", pm_delta_anomalies),
        ]
        extra_sources = [(name, rows) for name, rows in extra_sources if rows]

        anomaly_sources = {
            "cable": cable_anomalies,
            "xmit": xmit_anomalies,
            "ber": ber_anomalies,
            "hca": hca_anomalies,
            "fan": fan_anomalies,
            "histogram": histogram_anomalies,
            "routing": routing_anomalies,
            "qos": qos_anomalies,
            "mlnx_counters": mlnx_counters_anomalies,
            "pm_delta": pm_delta_anomalies,
            "pci_performance": pci_performance_anomalies,
        }
        anomaly_index_map = {
            name: self._build_anomaly_index(rows)
            for name, rows in anomaly_sources.items()
            if rows
        }
        analysis_index: Set[Tuple[str, Optional[int]]] = set()
        for key in ("cable", "xmit", "ber", "hca"):
            analysis_index.update(anomaly_index_map.get(key, set()))
        if analysis_index:
            anomaly_index_map["analysis"] = analysis_index

        datasets = {
            "analysis": analysis_rows,
            "cable": cable_rows,
            "xmit": xmit_rows,
            "link_oscillation": link_oscillation_rows,
            "ber": ber_rows,
            "hca": hca_rows,
            "fan": fan_rows,
            "histogram": histogram_rows,
            "switch": switch_rows,
            "routing": routing_rows,
            "qos": qos_rows,
            "sm_info": sm_info_rows,
            "port_hierarchy": port_hierarchy_rows,
            "mlnx_counters": mlnx_counters_rows,
            "pm_delta": pm_delta_rows,
            "vports": vports_rows,
            "pkey": pkey_rows,
            "system_info": system_info_rows,
            "extended_port_info": extended_port_info_rows,
            "ar_info": ar_info_rows,
            "sharp": sharp_rows,
            "fec_mode": fec_mode_rows,
            "phy_diagnostics": phy_diagnostics_rows,
            "neighbors": neighbors_rows,
            "buffer_histogram": buffer_histogram_rows,
            "extended_node_info": extended_node_info_rows,
            "extended_switch_info": extended_switch_info_rows,
            "power_sensors": power_sensors_rows,
            "routing_config": routing_config_rows,
            "temp_alerts": temp_alerts_rows,
            "credit_watchdog": credit_watchdog_rows,
            "pci_performance": pci_performance_rows,
            "per_lane_performance": per_lane_performance_rows,
            "n2n_security": n2n_security_rows,
        }
        dataset_totals = {name: len(rows) for name, rows in datasets.items()}
        filtered_datasets = {
            name: self._filter_anomalies(name, rows, anomaly_index_map.get(name))
            for name, rows in datasets.items()
        }
        analysis_rows = filtered_datasets["analysis"]
        cable_rows = filtered_datasets["cable"]
        xmit_rows = filtered_datasets["xmit"]
        ber_rows = filtered_datasets["ber"]
        hca_rows = filtered_datasets["hca"]
        fan_rows = filtered_datasets["fan"]
        histogram_rows = filtered_datasets["histogram"]
        switch_rows = filtered_datasets["switch"]
        routing_rows = filtered_datasets["routing"]
        qos_rows = filtered_datasets["qos"]
        sm_info_rows = filtered_datasets["sm_info"]
        port_hierarchy_rows = filtered_datasets["port_hierarchy"]
        mlnx_counters_rows = filtered_datasets["mlnx_counters"]
        pm_delta_rows = filtered_datasets["pm_delta"]
        vports_rows = filtered_datasets["vports"]
        pkey_rows = filtered_datasets["pkey"]
        system_info_rows = filtered_datasets["system_info"]
        extended_port_info_rows = filtered_datasets["extended_port_info"]
        ar_info_rows = filtered_datasets["ar_info"]
        sharp_rows = filtered_datasets["sharp"]
        fec_mode_rows = filtered_datasets["fec_mode"]
        phy_diagnostics_rows = filtered_datasets["phy_diagnostics"]
        neighbors_rows = filtered_datasets["neighbors"]
        buffer_histogram_rows = filtered_datasets["buffer_histogram"]
        extended_node_info_rows = filtered_datasets["extended_node_info"]
        extended_switch_info_rows = filtered_datasets["extended_switch_info"]
        power_sensors_rows = filtered_datasets["power_sensors"]
        routing_config_rows = filtered_datasets["routing_config"]
        temp_alerts_rows = filtered_datasets["temp_alerts"]
        credit_watchdog_rows = filtered_datasets["credit_watchdog"]
        pci_performance_rows = filtered_datasets["pci_performance"]
        per_lane_performance_rows = filtered_datasets["per_lane_performance"]
        n2n_security_rows = filtered_datasets["n2n_security"]

        logger.info("Calculating health score...")
        health_report = calculate_health_score(
            analysis_data=analysis_rows,
            cable_data=cable_rows,
            xmit_data=xmit_rows,
            ber_data=ber_rows,
            hca_data=hca_rows,
            fan_data=fan_rows,
            histogram_data=histogram_rows,
            extra_sources=extra_sources,
        )
        health = health_report_to_dict(health_report)

        issues = [
            {
                "severity": issue.severity.value,
                "category": issue.category,
                "description": issue.description,
                "node_guid": issue.node_guid,
                "port_number": issue.port_number,
                "weight": issue.weight,
                "details": issue.details,
            }
            for issue in health_report.issues
        ]

        warnings_by_category = warnings_analysis.get("by_category", {})
        warnings_summary = warnings_analysis.get("summary", {})

        def preview_full(name: str) -> List[Dict[str, object]]:
            return self._preview_records(datasets.get(name, []))

        def preview_issues(name: str) -> List[Dict[str, object]]:
            return self._preview_records(filtered_datasets.get(name, []))

        analysis_full_rows = datasets.get("analysis", [])
        payload = {
            "health": health,
            "data": self._preview_records(analysis_full_rows),
            "data_issue_rows": self._preview_records(analysis_rows),
            "cable_summary": cable_summary,
            "switch_summary": switch_analysis.summary,
            "routing_summary": routing_analysis.summary,
            "xmit_summary": getattr(xmit_analysis, "summary", {}),
            "link_oscillation_summary": link_oscillation_analysis.summary,
            "histogram_summary": getattr(histogram_analysis, "summary", {}),
            "qos_summary": qos_analysis.summary,
            "sm_info_summary": sm_info_analysis.summary,
            "port_hierarchy_summary": port_hierarchy_analysis.summary,
            "mlnx_counters_summary": mlnx_counters_analysis.summary,
            "pm_delta_summary": pm_delta_analysis.summary,
            "vports_summary": vports_analysis.summary,
            "pkey_summary": pkey_analysis.summary,
            "system_info_summary": system_info_analysis.summary,
            "extended_port_info_summary": extended_port_info_analysis.summary,
            "ar_info_summary": ar_info_analysis.summary,
            "sharp_summary": sharp_analysis.summary,
            "fec_mode_summary": fec_mode_analysis.summary,
            "phy_diagnostics_summary": phy_diagnostics_analysis.summary,
            "neighbors_summary": neighbors_analysis.summary,
            "buffer_histogram_summary": buffer_histogram_analysis.summary,
            "extended_node_info_summary": extended_node_info_analysis.summary,
            "extended_switch_info_summary": extended_switch_info_analysis.summary,
            "power_sensors_summary": power_sensors_analysis.summary,
            "routing_config_summary": routing_config_analysis.summary,
            "temp_alerts_summary": temp_alerts_analysis.summary,
            "credit_watchdog_summary": credit_watchdog_analysis.summary,
            "pci_performance_summary": pci_performance_analysis.summary,
            "per_lane_performance_summary": per_lane_performance_analysis.summary,
            "n2n_security_summary": n2n_security_analysis.summary,
            "warnings_by_category": warnings_by_category,
            "warnings_summary": warnings_summary,
            "debug_stdout": brief_payload.get("debug_stdout", ""),
            "debug_stderr": brief_payload.get("debug_stderr", ""),
            "preview_row_limit": MAX_PREVIEW_ROWS,
            "data_total_rows": dataset_totals.get("analysis", len(analysis_full_rows)),
        }

        dataset_aliases = {
            "cable": "cable",
            "xmit": "xmit",
            "link_oscillation": "link_oscillation",
            "ber": "ber",
            "hca": "hca",
            "fan": "fan",
            "histogram": "histogram",
            "switch": "switch",
            "routing": "routing",
            "qos": "qos",
            "sm_info": "sm_info",
            "port_hierarchy": "port_hierarchy",
            "mlnx_counters": "mlnx_counters",
            "pm_delta": "pm_delta",
            "vports": "vports",
            "pkey": "pkey",
            "system_info": "system_info",
            "extended_port_info": "extended_port_info",
            "ar_info": "ar_info",
            "sharp": "sharp",
            "fec_mode": "fec_mode",
            "phy_diagnostics": "phy_diagnostics",
            "neighbors": "neighbors",
            "buffer_histogram": "buffer_histogram",
            "extended_node_info": "extended_node_info",
            "extended_switch_info": "extended_switch_info",
            "power_sensors": "power_sensors",
            "routing_config": "routing_config",
            "temp_alerts": "temp_alerts",
            "credit_watchdog": "credit_watchdog",
            "pci_performance": "pci_performance",
            "per_lane_performance": "per_lane_performance",
            "n2n_security": "n2n_security",
        }

        for dataset_name, alias in dataset_aliases.items():
            payload[f"{alias}_data"] = preview_full(dataset_name)
            payload[f"{alias}_issue_rows"] = preview_issues(dataset_name)
            payload[f"{alias}_total_rows"] = dataset_totals.get(
                dataset_name, len(datasets.get(dataset_name, []))
            )
        payload["issues"] = issues
        return self._sanitize(payload)

    def _run_cable_service(self, target_dir: Path):
        service = CableService(dataset_root=target_dir)
        return service.run()

    def _run_xmit_service(self, target_dir: Path):
        service = XmitService(dataset_root=target_dir)
        return service.run()

    def _run_link_oscillation_service(self, target_dir: Path):
        service = LinkOscillationService(dataset_root=target_dir)
        return service.run()

    def _run_ber_service(self, target_dir: Path):
        cached = self._get_cached_service_result("ber", target_dir)
        if cached is not None:
            logger.debug("Reusing cached BER analysis for dataset %s", target_dir)
            return cached
        service = BerService(dataset_root=target_dir)
        result = service.run()
        self._set_cached_service_result("ber", target_dir, result)
        return result

    def _run_hca_service(self, target_dir: Path) -> Tuple[List[Dict[str, object]], pd.DataFrame]:
        service = HcaService(dataset_root=target_dir)
        data = service.run()
        anomalies = service.build_anomalies()
        return data, anomalies

    def _run_fan_service(self, target_dir: Path):
        service = FanService(dataset_root=target_dir)
        return service.run()

    def _run_histogram_service(self, target_dir: Path):
        service = HistogramService(dataset_root=target_dir)
        return service.run()

    def _run_warnings_service(self, target_dir: Path):
        service = WarningsService(dataset_root=target_dir)
        analysis = service.run()
        return {
            "by_category": service.get_warnings_by_category(),
            "summary": service.get_summary_dict(),
        }

    def _run_switch_service(self, target_dir: Path):
        service = SwitchService(dataset_root=target_dir)
        return service.run()

    def _run_routing_service(self, target_dir: Path):
        service = RoutingService(dataset_root=target_dir)
        return service.run()

    def _run_qos_service(self, target_dir: Path):
        service = QosService(dataset_root=target_dir)
        return service.run()

    def _run_sm_info_service(self, target_dir: Path):
        service = SMInfoService(dataset_root=target_dir)
        return service.run()

    def _run_port_hierarchy_service(self, target_dir: Path):
        service = PortHierarchyService(dataset_root=target_dir)
        return service.run()

    def _run_mlnx_counters_service(self, target_dir: Path):
        service = MlnxCountersService(dataset_root=target_dir)
        return service.run()

    def _run_pm_delta_service(self, target_dir: Path):
        service = PmDeltaService(dataset_root=target_dir)
        return service.run()

    def _run_vports_service(self, target_dir: Path):
        service = VPortsService(dataset_root=target_dir)
        return service.run()

    def _run_pkey_service(self, target_dir: Path):
        service = PkeyService(dataset_root=target_dir)
        return service.run()

    def _run_system_info_service(self, target_dir: Path):
        service = SystemInfoService(dataset_root=target_dir)
        return service.run()

    def _run_extended_port_info_service(self, target_dir: Path):
        service = ExtendedPortInfoService(dataset_root=target_dir)
        return service.run()

    def _run_ar_info_service(self, target_dir: Path):
        service = ArInfoService(dataset_root=target_dir)
        return service.run()

    def _run_sharp_service(self, target_dir: Path):
        service = SharpService(dataset_root=target_dir)
        return service.run()

    def _run_fec_mode_service(self, target_dir: Path):
        service = FecModeService(dataset_root=target_dir)
        return service.run()

    def _run_phy_diagnostics_service(self, target_dir: Path):
        service = PhyDiagnosticsService(dataset_root=target_dir)
        return service.run()

    def _run_neighbors_service(self, target_dir: Path):
        service = NeighborsService(dataset_root=target_dir)
        return service.run()

    def _run_buffer_histogram_service(self, target_dir: Path):
        service = BufferHistogramService(dataset_root=target_dir)
        return service.run()

    def _run_extended_node_info_service(self, target_dir: Path):
        service = ExtendedNodeInfoService(dataset_root=target_dir)
        return service.run()

    def _run_extended_switch_info_service(self, target_dir: Path):
        service = ExtendedSwitchInfoService(dataset_root=target_dir)
        return service.run()

    def _run_power_sensors_service(self, target_dir: Path):
        service = PowerSensorsService(dataset_root=target_dir)
        return service.run()

    def _run_routing_config_service(self, target_dir: Path):
        service = RoutingConfigService(dataset_root=target_dir)
        return service.run()

    def _run_temp_alerts_service(self, target_dir: Path):
        service = TempAlertsService(dataset_root=target_dir)
        return service.run()

    def _run_credit_watchdog_service(self, target_dir: Path):
        service = CreditWatchdogService(dataset_root=target_dir)
        return service.run()

    def _run_pci_performance_service(self, target_dir: Path):
        service = PciPerformanceService(dataset_root=target_dir)
        return service.run()


    def _run_per_lane_performance_service(self, target_dir: Path):
        service = PerLanePerformanceService(dataset_root=target_dir)
        return service.run()

    def _run_n2n_security_service(self, target_dir: Path):
        service = N2NSecurityService(dataset_root=target_dir)
        return service.run()

    def _build_brief(
        self,
        xmit_rows: List[Dict[str, object]],
        cable_rows: List[Dict[str, object]],
        ber_rows: List[Dict[str, object]],
        hca_rows: List[Dict[str, object]],
    ) -> Dict[str, object]:
        service = BriefService()
        result = service.run(
            xmit_rows=xmit_rows,
            cable_rows=cable_rows,
            ber_rows=ber_rows,
            hca_rows=hca_rows,
        )
        return {"data": result.data, "debug_stdout": result.debug_stdout, "debug_stderr": result.debug_stderr}

    def _flatten_anomaly_records(self, frame: Optional[pd.DataFrame]) -> List[Dict[str, object]]:
        if frame is None or frame.empty:
            return []
        value_columns = [col for col in frame.columns if col not in IBH_ANOMALY_TBL_KEY]
        if not value_columns:
            return []
        rows: List[Dict[str, object]] = []
        for _, row in frame.iterrows():
            node_guid = row.get("NodeGUID", "")
            port_number = self._safe_port(row.get("PortNumber"))
            for column in value_columns:
                anomaly_type = self._column_to_anomaly(column)
                if anomaly_type is None:
                    continue
                weight = self._safe_float(row.get(column))
                if weight <= 0:
                    continue
                rows.append(
                    {
                        "NodeGUID": node_guid,
                        "PortNumber": port_number if port_number is not None else 0,
                        IBH_ANOMALY_AGG_COL: anomaly_type.value,
                        IBH_ANOMALY_AGG_WEIGHT: weight,
                    }
                )
        return rows

    def _filter_anomalies(
        self,
        dataset_name: str,
        rows: List[Dict[str, object]],
        anomaly_index: Optional[Set[Tuple[str, Optional[int]]]] = None,
    ) -> List[Dict[str, object]]:
        if not rows:
            return []
        preview = self._preview_records
        if dataset_name in {"ber", "analysis", "link_oscillation"}:
            return preview(rows)
        if anomaly_index:
            matched = [row for row in rows if self._row_matches_anomaly_index(row, anomaly_index)]
            if matched:
                return preview(matched)
        heuristic_rows = [row for row in rows if self._row_has_anomaly_markers(row)]
        if heuristic_rows:
            return preview(heuristic_rows)
        return preview(rows)

    def _build_anomaly_index(self, anomaly_rows: List[Dict[str, object]]) -> Set[Tuple[str, Optional[int]]]:
        index: Set[Tuple[str, Optional[int]]] = set()
        for row in anomaly_rows:
            guid = self._normalize_guid_token(row.get("NodeGUID"))
            port = self._safe_port(row.get("PortNumber"))
            normalized_port = None if port in (None, 0) else port
            if guid or normalized_port is not None:
                index.add((guid, normalized_port))
        return index

    def _row_matches_anomaly_index(
        self,
        row: Dict[str, object],
        anomaly_index: Set[Tuple[str, Optional[int]]],
    ) -> bool:
        if not anomaly_index:
            return False
        guid = self._extract_guid_from_row(row)
        port = self._extract_port_from_row(row)
        normalized_port = None if port in (None, 0) else port
        candidates = [(guid, normalized_port)]
        candidates.append((guid, None))
        if not guid:
            candidates.append(("", normalized_port))
            candidates.append(("", None))
        for candidate in candidates:
            if candidate in anomaly_index:
                return True
        return False

    def _extract_guid_from_row(self, row: Dict[str, object]) -> str:
        guid_keys = (
            "NodeGUID",
            "node_guid",
            "Node Guid",
            "NodeGuid",
            "GUID",
            "Guid",
        )
        for key in guid_keys:
            if key in row:
                value = row.get(key)
                if value is not None and str(value).strip():
                    return self._normalize_guid_token(value)
        return ""

    def _extract_port_from_row(self, row: Dict[str, object]) -> Optional[int]:
        port_keys = (
            "PortNumber",
            "PortNum",
            "Port",
            "Port Number",
            "Port #",
            "PortId",
            "PortID",
        )
        for key in port_keys:
            if key in row:
                port_value = self._safe_port(row.get(key))
                if port_value is not None:
                    return port_value
        return None

    def _normalize_guid_token(self, value: object) -> str:
        if value is None:
            return ""
        text = str(value).strip().lower()
        if not text or text in {"none", "null"}:
            return ""
        if text.startswith("0x"):
            return text
        try:
            return hex(int(text, 16))
        except (ValueError, TypeError):
            return text

    def _row_has_anomaly_markers(self, row: Dict[str, object]) -> bool:
        severity_normal = {"", "normal", "info", "ok", "pass", "healthy", "none"}
        numeric_keywords = (
            "error",
            "fail",
            "linkdown",
            "downed",
            "down_count",
            "recovery",
            "alarm",
            "warning",
            "anomaly",
            "icrc",
            "parity",
            "discard",
            "drop",
            "timeout",
            "mismatch",
            "violation",
            "unhealthy",
            "problem",
            "issue",
            "retry",
            "fault",
            "alert",
        )
        negative_value_tokens = (
            "fail",
            "error",
            "warning",
            "critical",
            "alarm",
            "down",
            "inactive",
            "not active",
            "mismatch",
            "unsupported",
            "timeout",
            "asym",
            "asymmetric",
            "unhealthy",
            "degraded",
            "violation",
            "missing",
            "not present",
            "fault",
            "bad",
            "exceeded",
        )
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                continue
            key_lower = str(key).lower()
            if "anomaly" in key_lower:
                if self._value_indicates_problem(value):
                    return True
                continue
            if "severity" in key_lower:
                severity = str(value).strip().lower()
                if severity and severity not in severity_normal:
                    return True
                continue
            if key_lower in {"issues", "issue", "problems", "alerts"}:
                if self._value_indicates_problem(value):
                    return True
                continue
            if any(keyword in key_lower for keyword in numeric_keywords):
                if "threshold" in key_lower or "limit" in key_lower:
                    continue
                if self._value_indicates_problem(value):
                    return True
                continue
            if any(token in (str(value).strip().lower() if isinstance(value, str) else "") for token in negative_value_tokens):
                return True
        return False

    def _value_indicates_problem(self, value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, numbers.Number):
            numeric = float(value)
            if math.isnan(numeric) or math.isinf(numeric):
                return False
            return numeric != 0.0
        text = str(value).strip().lower()
        if not text:
            return False
        if text in {"0", "false", "off", "normal", "none", "ok", "pass", "healthy"}:
            return False
        return True


    @staticmethod
    def _column_to_anomaly(column: str) -> Optional[AnomlyType]:
        for atype in AnomlyType:
            if str(atype) == column or atype.value == column:
                return atype
        return None

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(numeric) or math.isinf(numeric):
            return 0.0
        return numeric

    @staticmethod
    def _safe_port(value: object) -> Optional[int]:
        try:
            if value is None:
                return None
            if isinstance(value, float) and math.isnan(value):
                return None
            if isinstance(value, str) and not value.strip():
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _preview_records(self, records: List[Dict[str, object]]) -> List[Dict[str, object]]:
        if not records:
            return records
        if MAX_PREVIEW_ROWS is None:
            return records
        if len(records) <= MAX_PREVIEW_ROWS:
            return records
        return records[:MAX_PREVIEW_ROWS]

    def _sanitize(self, value):
        if isinstance(value, dict):
            return {key: self._sanitize(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if hasattr(value, "item"):
            try:
                return self._sanitize(value.item())
            except Exception:
                pass
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        if isinstance(value, numbers.Integral):
            return int(value)
        if isinstance(value, numbers.Real):
            numeric = float(value)
            if math.isnan(numeric) or math.isinf(numeric):
                return None
            return numeric
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.isoformat()
        return value
