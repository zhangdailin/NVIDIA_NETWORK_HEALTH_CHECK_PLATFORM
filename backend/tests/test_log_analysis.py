import unittest
import tempfile
import shutil
import os
from pathlib import Path
from backend.services.log_analysis_service import LogAnalysisService

class TestLogAnalysisService(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.log_file = self.test_dir / "ibdiagnet2.log"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_analyze_log(self):
        content = """
Some info
-E- Error 1
-I- Some info
-W- Warning 1
-I- Fabric Qualities Report:
-I- Credit Loops Report:
-I- no credit loops found
"""
        with open(self.log_file, "w") as f:
            f.write(content)

        service = LogAnalysisService(self.test_dir)
        result = service.analyze()

        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0], "-E- Error 1")
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["warnings"][0], "-W- Warning 1")
        
        # Check routing summary
        self.assertTrue(any("Fabric Qualities Report" in s for s in result["routing_summary"]))
        self.assertTrue(any("Credit Loops Report" in s for s in result["routing_summary"]))
        self.assertTrue(any("no credit loops found" in s for s in result["routing_summary"]))

if __name__ == "__main__":
    unittest.main()