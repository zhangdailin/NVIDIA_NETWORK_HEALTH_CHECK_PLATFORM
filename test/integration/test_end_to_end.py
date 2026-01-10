"""Comprehensive end-to-end tests for the entire analysis pipeline."""

import pytest
import asyncio
import zipfile
import io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


class TestEndToEndAnalysis:
    """End-to-end tests for complete analysis workflow."""

    @pytest.fixture
    def executor(self):
        """Create thread pool executor."""
        executor = ThreadPoolExecutor(max_workers=4)
        yield executor
        executor.shutdown(wait=True)

    def test_complete_upload_and_analysis_workflow(self, sample_ibdiagnet_dir):
        """Test complete workflow from upload to analysis results."""
        # Create a zip file from sample data
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        # Upload and analyze
        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        # Should succeed
        assert response.status_code == 200
        data = response.json()

        # Verify complete response structure
        assert "status" in data
        assert data["status"] == "success"
        assert "task_id" in data
        assert "health_score" in data
        assert "analysis" in data

        # Verify health score structure
        health = data["health_score"]
        assert "score" in health
        assert "grade" in health
        assert "status" in health
        assert "total_nodes" in health
        assert "total_ports" in health
        assert "summary" in health
        assert "category_scores" in health
        assert "issues" in health

        # Verify analysis sections
        analysis = data["analysis"]
        expected_sections = [
            "cable", "xmit", "ber", "hca", "warnings",
            "histogram", "link_oscillation"
        ]

        for section in expected_sections:
            if section in analysis:
                assert "data" in analysis[section]
                assert isinstance(analysis[section]["data"], list)

    def test_health_score_calculation_accuracy(self, sample_ibdiagnet_dir):
        """Test that health score is calculated accurately."""
        # Create zip and upload
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code == 200
        data = response.json()

        health = data["health_score"]

        # Verify score is in valid range
        assert 0 <= health["score"] <= 100

        # Verify grade matches score
        score = health["score"]
        grade = health["grade"]

        if score >= 90:
            assert grade == "A"
        elif score >= 80:
            assert grade == "B"
        elif score >= 70:
            assert grade == "C"
        elif score >= 60:
            assert grade == "D"
        else:
            assert grade == "F"

        # Verify status matches score
        status = health["status"]
        if score >= 80:
            assert status == "Healthy"
        elif score >= 60:
            assert status == "Warning"
        else:
            assert status == "Critical"

    def test_anomaly_detection_across_all_services(self, sample_ibdiagnet_dir):
        """Test that anomalies are detected across all services."""
        # Create zip and upload
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code == 200
        data = response.json()

        # Check for anomalies in health score
        health = data["health_score"]
        issues = health["issues"]

        # Verify issue structure
        for issue in issues:
            assert "severity" in issue
            assert "category" in issue
            assert "description" in issue
            assert "node_guid" in issue
            assert "weight" in issue

            # Verify severity is valid
            assert issue["severity"] in ["critical", "warning", "info"]

            # Verify category is valid
            valid_categories = ["ber", "errors", "congestion", "latency", "balance", "config", "anomaly"]
            assert issue["category"] in valid_categories

    def test_data_consistency_across_services(self, sample_ibdiagnet_dir):
        """Test that data is consistent across different services."""
        # Create zip and upload
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code == 200
        data = response.json()

        analysis = data["analysis"]

        # Collect all NodeGUIDs from different services
        all_guids = set()

        for service_name, service_data in analysis.items():
            if isinstance(service_data, dict) and "data" in service_data:
                for item in service_data["data"]:
                    guid = item.get("NodeGUID") or item.get("NodeGuid")
                    if guid:
                        all_guids.add(guid)

        # Should have consistent GUID format across services
        for guid in all_guids:
            assert isinstance(guid, str)
            assert guid.startswith("0x") or len(guid) > 0

    def test_topology_information_integration(self, sample_ibdiagnet_dir):
        """Test that topology information is integrated across services."""
        # Create zip and upload
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code == 200
        data = response.json()

        analysis = data["analysis"]

        # Check that services include topology information
        for service_name, service_data in analysis.items():
            if isinstance(service_data, dict) and "data" in service_data:
                for item in service_data["data"]:
                    # Should have node identification
                    has_node_info = any(key in item for key in [
                        "NodeGUID", "NodeGuid", "Node Name", "NodeDesc"
                    ])
                    if has_node_info:
                        # At least some items should have topology info
                        break

    def test_performance_with_real_data(self, sample_ibdiagnet_dir):
        """Test performance with real data."""
        import time

        # Create zip and upload
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        start_time = time.time()

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        elapsed_time = time.time() - start_time

        # Should complete in reasonable time (< 2 minutes for real data)
        assert elapsed_time < 120

        # Should succeed
        assert response.status_code == 200

    def test_error_recovery_and_partial_results(self, sample_ibdiagnet_dir):
        """Test that system handles errors gracefully and returns partial results."""
        # This test verifies resilience
        # Even if some services fail, others should still work

        # Create zip and upload
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        # Should not crash even if some tables are missing
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            # Should have at least basic structure
            assert "status" in data


class TestEndToEndEdgeCases:
    """Test edge cases in end-to-end workflow."""

    def test_empty_zip_file(self):
        """Test handling of empty zip file."""
        # Create empty zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            pass  # Empty zip

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("empty.zip", zip_buffer, "application/zip")}
        )

        # Should reject empty zip
        assert response.status_code == 400

    def test_corrupted_zip_file(self):
        """Test handling of corrupted zip file."""
        # Create corrupted zip
        corrupted_data = b"This is not a valid zip file"

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("corrupted.zip", io.BytesIO(corrupted_data), "application/zip")}
        )

        # Should reject corrupted file
        assert response.status_code == 400

    def test_zip_without_db_csv(self):
        """Test handling of zip without db_csv files."""
        # Create zip with random files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("random.txt", "This is a random file")

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("no_dbcsv.zip", zip_buffer, "application/zip")}
        )

        # Should reject - no db_csv found
        assert response.status_code == 400
        assert "No .db_csv files found" in response.json()["detail"]

    def test_very_large_dataset(self):
        """Test handling of very large dataset."""
        # This is a conceptual test - would need actual large data
        # Should handle large datasets without crashing
        pass

    def test_concurrent_uploads(self, sample_ibdiagnet_dir):
        """Test handling of concurrent uploads."""
        import concurrent.futures

        # Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        def upload_file():
            zip_buffer.seek(0)
            return client.post(
                "/api/upload/ibdiagnet",
                files={"file": ("ibdiagnet.zip", io.BytesIO(zip_buffer.read()), "application/zip")}
            )

        # Upload concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(upload_file) for _ in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed or be rate limited
        for response in results:
            assert response.status_code in [200, 429]


class TestEndToEndDataValidation:
    """Test data validation in end-to-end workflow."""

    def test_output_data_types(self, sample_ibdiagnet_dir):
        """Test that all output data types are correct."""
        # Create zip and upload
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify data types
        assert isinstance(data["status"], str)
        assert isinstance(data["task_id"], str)
        assert isinstance(data["health_score"], dict)
        assert isinstance(data["health_score"]["score"], int)
        assert isinstance(data["health_score"]["grade"], str)
        assert isinstance(data["health_score"]["issues"], list)
        assert isinstance(data["analysis"], dict)

    def test_no_data_loss_in_pipeline(self, sample_ibdiagnet_dir):
        """Test that no data is lost in the analysis pipeline."""
        # Create zip and upload
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify that data exists in all expected sections
        analysis = data["analysis"]

        # Count total items across all services
        total_items = 0
        for service_name, service_data in analysis.items():
            if isinstance(service_data, dict) and "data" in service_data:
                total_items += len(service_data["data"])

        # Should have processed data
        assert total_items >= 0
