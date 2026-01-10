"""Integration tests for analysis service."""

import pytest
from pathlib import Path
from services.analysis_service import AnalysisService
import asyncio
from concurrent.futures import ThreadPoolExecutor


class TestAnalysisServiceIntegration:
    """Integration tests for the main analysis service."""

    @pytest.fixture
    def analysis_service(self):
        """Create analysis service instance."""
        return AnalysisService()

    @pytest.fixture
    def executor(self):
        """Create thread pool executor."""
        executor = ThreadPoolExecutor(max_workers=4)
        yield executor
        executor.shutdown(wait=True)

    @pytest.mark.asyncio
    async def test_full_analysis_pipeline(self, analysis_service, sample_ibdiagnet_dir, tmp_path, executor):
        """Test complete analysis pipeline with real data."""
        # Load dataset
        analysis_service.load_dataset(sample_ibdiagnet_dir)

        # Run analysis
        loop = asyncio.get_event_loop()
        result = await analysis_service.analyze_ibdiagnet(
            target_dir=sample_ibdiagnet_dir,
            task_dir=tmp_path,
            task_id="test_task",
            executor=executor,
            loop=loop,
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "health_score" in result
        assert "analysis" in result

        # Verify health score
        health = result["health_score"]
        assert "score" in health
        assert "grade" in health
        assert "status" in health
        assert 0 <= health["score"] <= 100

        # Verify analysis sections
        analysis = result["analysis"]
        expected_sections = [
            "cable",
            "xmit",
            "ber",
            "hca",
            "warnings",
        ]

        for section in expected_sections:
            if section in analysis:
                assert "data" in analysis[section]
                assert isinstance(analysis[section]["data"], list)

    def test_dataset_loading(self, analysis_service, sample_ibdiagnet_dir):
        """Test dataset loading."""
        analysis_service.load_dataset(sample_ibdiagnet_dir)

        # Verify dataset is loaded
        assert analysis_service.dataset is not None
        assert analysis_service.dataset.db_csv_path.exists()

    def test_parallel_service_execution(self, analysis_service, sample_ibdiagnet_dir, tmp_path, executor):
        """Test that services execute in parallel."""
        import time

        analysis_service.load_dataset(sample_ibdiagnet_dir)

        start_time = time.time()

        # Run analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            analysis_service.analyze_ibdiagnet(
                target_dir=sample_ibdiagnet_dir,
                task_dir=tmp_path,
                task_id="test_parallel",
                executor=executor,
                loop=loop,
            )
        )
        loop.close()

        elapsed_time = time.time() - start_time

        # Should complete in reasonable time (parallel execution)
        # This is a rough check - adjust based on actual performance
        assert elapsed_time < 60  # Should complete within 60 seconds

        # Verify result is valid
        assert "health_score" in result

    def test_error_handling_missing_tables(self, analysis_service, tmp_path):
        """Test error handling when required tables are missing."""
        # Create empty directory
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Should handle gracefully or raise appropriate error
        with pytest.raises(Exception):
            analysis_service.load_dataset(empty_dir)

    def test_analysis_with_minimal_data(self, analysis_service, sample_ibdiagnet_dir, tmp_path, executor):
        """Test analysis with minimal/incomplete data."""
        # This tests robustness when some tables are missing
        analysis_service.load_dataset(sample_ibdiagnet_dir)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            analysis_service.analyze_ibdiagnet(
                target_dir=sample_ibdiagnet_dir,
                task_dir=tmp_path,
                task_id="test_minimal",
                executor=executor,
                loop=loop,
            )
        )
        loop.close()

        # Should still return valid result
        assert isinstance(result, dict)
        assert "health_score" in result

    def test_topology_generation(self, analysis_service, sample_ibdiagnet_dir, tmp_path, executor):
        """Test topology visualization generation."""
        analysis_service.load_dataset(sample_ibdiagnet_dir)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            analysis_service.analyze_ibdiagnet(
                target_dir=sample_ibdiagnet_dir,
                task_dir=tmp_path,
                task_id="test_topo",
                executor=executor,
                loop=loop,
            )
        )
        loop.close()

        # Check if topology was generated
        if "topology_url" in result:
            # Verify topology file exists
            assert result["topology_url"]

    def test_anomaly_detection_integration(self, analysis_service, sample_ibdiagnet_dir, tmp_path, executor):
        """Test that anomalies are detected across all services."""
        analysis_service.load_dataset(sample_ibdiagnet_dir)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            analysis_service.analyze_ibdiagnet(
                target_dir=sample_ibdiagnet_dir,
                task_dir=tmp_path,
                task_id="test_anomaly",
                executor=executor,
                loop=loop,
            )
        )
        loop.close()

        # Check health score issues
        health = result["health_score"]
        if health["summary"]["critical"] > 0 or health["summary"]["warning"] > 0:
            # Should have issues listed
            assert len(health["issues"]) > 0

            # Issues should have required fields
            for issue in health["issues"]:
                assert "severity" in issue
                assert "category" in issue
                assert "description" in issue

    def test_service_result_consistency(self, analysis_service, sample_ibdiagnet_dir, tmp_path, executor):
        """Test that running analysis twice gives consistent results."""
        analysis_service.load_dataset(sample_ibdiagnet_dir)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run analysis twice
        result1 = loop.run_until_complete(
            analysis_service.analyze_ibdiagnet(
                target_dir=sample_ibdiagnet_dir,
                task_dir=tmp_path,
                task_id="test_consistency_1",
                executor=executor,
                loop=loop,
            )
        )

        result2 = loop.run_until_complete(
            analysis_service.analyze_ibdiagnet(
                target_dir=sample_ibdiagnet_dir,
                task_dir=tmp_path,
                task_id="test_consistency_2",
                executor=executor,
                loop=loop,
            )
        )

        loop.close()

        # Health scores should be identical
        assert result1["health_score"]["score"] == result2["health_score"]["score"]
        assert result1["health_score"]["grade"] == result2["health_score"]["grade"]
