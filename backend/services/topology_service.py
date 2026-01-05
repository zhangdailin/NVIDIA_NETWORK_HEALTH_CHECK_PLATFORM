"""Simple topology renderer using vis-network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


class TopologyService:
    """Generates a lightweight HTML topology view from xmit data."""

    def render(
        self,
        *,
        xmit_rows: List[Dict[str, object]],
        issues: List[Dict[str, object]],
        output_file: Path,
    ) -> None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        severity_map = self._build_issue_map(issues)
        nodes, edges = self._build_graph(xmit_rows, severity_map)
        html = self._build_html(nodes, edges)
        output_file.write_text(html, encoding="utf-8")

    def _build_issue_map(self, issues: List[Dict[str, object]]) -> Dict[str, str]:
        ranking = {"critical": 2, "warning": 1, "info": 0}
        best: Dict[str, str] = {}
        for issue in issues:
            guid = str(issue.get("node_guid") or "").lower()
            severity = issue.get("severity", "info")
            if not guid:
                continue
            if guid not in best or ranking[severity] > ranking[best[guid]]:
                best[guid] = severity
        return best

    def _build_graph(self, rows, severity_map):
        nodes = {}
        edges = []
        fabric_id = "Fabric"
        nodes[fabric_id] = {
            "id": fabric_id,
            "label": "Fabric",
            "color": "#2563eb",
        }
        for row in rows:
            node_guid = str(row.get("NodeGUID") or "").lower()
            node_name = row.get("Node Name") or node_guid or "Node"
            node_id = node_guid or node_name
            severity = severity_map.get(node_guid, "info")
            nodes[node_id] = {
                "id": node_id,
                "label": str(node_name),
                "color": self._color_for_severity(severity),
            }
            target_name = row.get("Attached To") or fabric_id
            target_id = str(target_name)
            if target_id not in nodes:
                nodes[target_id] = {
                    "id": target_id,
                    "label": str(target_name),
                    "color": "#64748b",
                }
            edges.append({"from": node_id, "to": target_id})
        return list(nodes.values()), edges

    @staticmethod
    def _color_for_severity(severity: str) -> str:
        if severity == "critical":
            return "#ef4444"
        if severity == "warning":
            return "#eab308"
        return "#22c55e"

    def _build_html(self, nodes, edges) -> str:
        nodes_json = json.dumps(nodes)
        edges_json = json.dumps(edges)
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Network Topology</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"></script>
  <link rel="stylesheet" href="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.css" />
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; }}
    #network {{ width: 100vw; height: 100vh; background-color: #111827; }}
    .legend {{ position: absolute; top: 16px; left: 16px; background: rgba(15, 23, 42, 0.8); padding: 12px; border-radius: 8px; }}
  </style>
</head>
<body>
  <div class="legend">
    <div>Critical = Red</div>
    <div>Warning = Yellow</div>
    <div>Healthy = Green</div>
  </div>
  <div id="network"></div>
  <script>
    const nodes = new vis.DataSet({nodes_json});
    const edges = new vis.DataSet({edges_json});
    const container = document.getElementById('network');
    const data = {{ nodes, edges }};
    const options = {{
      physics: {{ stabilization: true }},
      edges: {{ color: '#94a3b8' }},
      nodes: {{ shape: 'dot', size: 16, font: {{ color: '#e2e8f0' }} }},
    }};
    new vis.Network(container, data, options);
  </script>
</body>
</html>"""
