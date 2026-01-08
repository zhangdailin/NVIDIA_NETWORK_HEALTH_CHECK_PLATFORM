import re
from pathlib import Path
from typing import List, Dict, Any

class LogAnalysisService:
    def __init__(self, upload_path: Path):
        self.log_path = upload_path / "ibdiagnet2.log"

    def analyze(self) -> Dict[str, Any]:
        if not self.log_path.exists():
            return {"error": "ibdiagnet2.log not found"}

        errors = []
        warnings = []
        routing_summary = []

        # Routing section markers
        in_routing_section = False
        routing_markers = [
            "Routing Validation",
            "Credit Loops Report",
            "Fabric Qualities Report"
        ]

        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Capture Errors
                    if line.startswith("-E-"):
                        errors.append(line)

                    # Capture Warnings
                    elif line.startswith("-W-"):
                        warnings.append(line)

                    # Check for routing section markers
                    if any(marker in line for marker in routing_markers):
                        in_routing_section = True
                        routing_summary.append(line)
                    elif in_routing_section:
                        # Capture lines within routing section
                        if line.startswith("-I-") or "credit loops" in line.lower():
                            routing_summary.append(line)
                        # Exit routing section on empty line or new section
                        elif line.startswith("---") or line.startswith("==="):
                            in_routing_section = False

        except Exception as e:
            return {"error": f"Failed to parse log: {str(e)}"}

        return {
            "errors": errors,
            "warnings": warnings,
            "routing_summary": routing_summary,
            "log_path": str(self.log_path.name)
        }
