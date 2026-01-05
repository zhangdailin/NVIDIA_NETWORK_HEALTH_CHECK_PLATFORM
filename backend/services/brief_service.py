"""Brief summary service aggregating multi-table insights."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


@dataclass
class BriefResult:
    data: List[Dict[str, object]]
    debug_stdout: str = ""
    debug_stderr: str = ""


class BriefService:
    """
    Builds the "analysis_data" table using xmit/cable/ber/hca snapshots.
    This is a simplified version of ib_analysis.brief merge logic that focuses
    on the columns our frontend renders in the "Analysis Brief" card.
    """

    def run(
        self,
        *,
        xmit_rows: List[Dict[str, object]],
        cable_rows: List[Dict[str, object]],
        ber_rows: List[Dict[str, object]],
        hca_rows: List[Dict[str, object]],
    ) -> BriefResult:
        xmit_df = pd.DataFrame(xmit_rows)
        merged = xmit_df.copy()

        for rows in [cable_rows, ber_rows]:
            if not rows:
                continue
            df = pd.DataFrame(rows)
            merged = pd.merge(merged, df, on=["NodeGUID", "PortNumber"], how="left", suffixes=("", "_dup"))

        if hca_rows:
            hca_df = pd.DataFrame(hca_rows)
            merged = pd.merge(merged, hca_df, on="NodeGUID", how="left", suffixes=("", "_hca"))

        merged["Index"] = range(1, len(merged) + 1)
        columns = [
            "Index",
            "NodeGUID",
            "Node Name",
            "Node Type",
            "PortNumber",
            "Attached To",
            "Attached To Type",
            "Attached To Port",
            "Xmit Wait",
            "Xmit Data",
            "PortState",
            "PortPhyState",
             "NeighborPortState",
             "NeighborPortPhyState",
            "LinkDownedCounter",
            "LinkErrorRecoveryCounter",
            "Temperature (c)",
            "Vendor",
            "PN",
            "FW",
            "FWInfo_PSID",
            "ActiveLinkWidth",
            "SupportedLinkWidth",
            "ActiveLinkSpeed",
            "SupportedLinkSpeed",
            "LinkComplianceStatus",
        ]
        existing_cols = [col for col in columns if col in merged.columns]
        brief_rows = merged[existing_cols].to_dict(orient="records")
        return BriefResult(data=brief_rows)
