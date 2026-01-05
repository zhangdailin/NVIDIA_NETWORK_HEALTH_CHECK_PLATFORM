"""Core analysis service that will replace direct ib_analysis usage."""

from __future__ import annotations

import asyncio
import datetime
import logging
import math
import numbers
from concurrent.futures import ThreadPoolExecutor
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .health_score import calculate_health_score, health_report_to_dict

import pandas as pd

from .anomalies import (
    IBH_ANOMALY_AGG_COL,
    IBH_ANOMALY_AGG_WEIGHT,
    IBH_ANOMALY_TBL_KEY,
    AnomlyType,
)
from .ber_service import BerService
from .brief_service import BriefService
from .cable_service import CableService
from .fan_service import FanService
from .hca_service import HcaService
from .histogram_service import HistogramService
from .topology_checker import TopologyChecker
from .topology_diff_service import TopologyDiffService
from .topology_service import TopologyService
from .xmit_service import XmitService

logger = logging.getLogger(__name__)

MAX_PREVIEW_ROWS = 2000

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
        path = (
            Path(expected_topology_path).expanduser()
            if expected_topology_path
            else self._default_expected_topology_path()
        )
        self._expected_topology_path = path if path and path.exists() else None

    def load_dataset(self, extracted_dir: Path) -> IbdiagnetDataset:
        extracted_dir = extracted_dir.resolve()
        dataset = self._dataset_cache.get(extracted_dir)
        if dataset is None:
            dataset = IbdiagnetDataset(root=extracted_dir)
            self._dataset_cache[extracted_dir] = dataset
        return dataset

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
        self.load_dataset(target_dir)
        loop = loop or asyncio.get_event_loop()
        topo_path = task_dir / "network.html"

        logger.info("Running native cable analysis...")
        cable_analysis = await loop.run_in_executor(
            executor,
            self._run_cable_service,
            target_dir,
        )

        logger.info("Running native xmit analysis...")
        xmit_analysis = await loop.run_in_executor(
            executor,
            self._run_xmit_service,
            target_dir,
        )

        logger.info("Running native BER analysis...")
        ber_analysis = await loop.run_in_executor(
            executor,
            self._run_ber_service,
            target_dir,
        )

        logger.info("Running native HCA analysis...")
        hca_data, hca_anomaly_df = await loop.run_in_executor(
            executor,
            self._run_hca_service,
            target_dir,
        )

        logger.info("Running native fan analysis...")
        fan_analysis = await loop.run_in_executor(
            executor,
            self._run_fan_service,
            target_dir,
        )

        logger.info("Running performance histogram analysis...")
        histogram_analysis = await loop.run_in_executor(
            executor,
            self._run_histogram_service,
            target_dir,
        )
        logger.info("All analyses completed")

        cable_rows = cable_analysis.data
        xmit_rows = xmit_analysis.data
        ber_rows = ber_analysis.data
        hca_rows = hca_data
        fan_rows = fan_analysis.data
        histogram_rows = histogram_analysis.data
        cable_anomalies = self._flatten_anomaly_records(cable_analysis.anomalies)
        xmit_anomalies = self._flatten_anomaly_records(xmit_analysis.anomalies)
        ber_anomalies = self._flatten_anomaly_records(ber_analysis.anomalies)
        hca_anomalies = self._flatten_anomaly_records(hca_anomaly_df)
        fan_anomalies = self._flatten_anomaly_records(fan_analysis.anomalies)
        histogram_anomalies = self._flatten_anomaly_records(histogram_analysis.anomalies)

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
        topology_checker = TopologyChecker(target_dir)
        topology_rows = topology_checker.to_issue_rows()
        topology_rows.extend(self._expected_topology_rows(target_dir))
        extra_sources = [
            ("cable", cable_anomalies),
            ("xmit", xmit_anomalies),
            ("ber", ber_anomalies),
            ("hca", hca_anomalies),
            ("fan", fan_anomalies),
            ("histogram", histogram_anomalies),
        ]
        extra_sources = [(name, rows) for name, rows in extra_sources if rows]

        logger.info("Calculating health score...")
        health_report = calculate_health_score(
            analysis_data=analysis_rows,
            cable_data=cable_rows,
            xmit_data=xmit_rows,
            ber_data=ber_rows,
            hca_data=hca_rows,
            fan_data=fan_rows,
            histogram_data=histogram_rows,
            topology_rows=topology_rows,
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

        logger.info("Generating topology visualization...")
        topo_service = TopologyService()
        await loop.run_in_executor(
            executor,
            lambda: topo_service.render(
                xmit_rows=xmit_rows,
                issues=issues,
                output_file=topo_path,
            ),
        )

        topo_url = f"/uploads/{task_id}/network.html" if topo_path.exists() else None
        analysis_total = len(analysis_rows)
        cable_total = len(cable_rows)
        xmit_total = len(xmit_rows)
        ber_total = len(ber_rows)
        hca_total = len(hca_rows)
        fan_total = len(fan_rows)
        histogram_total = len(histogram_rows)

        payload = {
            "health": health,
            "data": self._preview_records(analysis_rows),
            "cable_data": self._preview_records(cable_rows),
            "xmit_data": self._preview_records(xmit_rows),
            "ber_data": self._preview_records(ber_rows),
            "hca_data": self._preview_records(hca_rows),
            "fan_data": self._preview_records(fan_rows),
            "histogram_data": self._preview_records(histogram_rows),
            "topo_url": topo_url,
            "topology_data": topology_rows,
            "debug_stdout": brief_payload.get("debug_stdout", ""),
            "debug_stderr": brief_payload.get("debug_stderr", ""),
            "preview_row_limit": MAX_PREVIEW_ROWS,
            "data_total_rows": analysis_total,
            "cable_total_rows": cable_total,
            "xmit_total_rows": xmit_total,
            "ber_total_rows": ber_total,
            "hca_total_rows": hca_total,
            "fan_total_rows": fan_total,
            "histogram_total_rows": histogram_total,
        }
        return self._sanitize(payload)

    def _run_cable_service(self, target_dir: Path):
        service = CableService(dataset_root=target_dir)
        return service.run()

    def _run_xmit_service(self, target_dir: Path):
        service = XmitService(dataset_root=target_dir)
        return service.run()

    def _run_ber_service(self, target_dir: Path):
        service = BerService(dataset_root=target_dir)
        return service.run()

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

    def _expected_topology_rows(self, dataset_root: Path) -> List[Dict[str, object]]:
        if not self._expected_topology_path:
            return []
        try:
            service = TopologyDiffService(
                dataset_root=dataset_root,
                expected_topology_file=self._expected_topology_path,
            )
            return service.diff_rows()
        except FileNotFoundError:
            logger.warning("Expected topology file %s not found", self._expected_topology_path)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to compute topology diff: %s", exc)
        return []

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
