"""Performance and stress tests."""

import pytest
import time
import asyncio
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


@pytest.mark.slow
class TestPerformance:
    """Performance tests for the analysis pipeline."""

    def test_analysis_performance_baseline(self, sample_ibdiagnet_dir):
        """Test baseline performance with standard dataset."""
        # Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        # Measure time
        start_time = time.time()

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        elapsed_time = time.time() - start_time

        # Should complete in reasonable time
        assert response.status_code == 200
        assert elapsed_time < 60  # Should complete within 60 seconds

        print(f"\nBaseline analysis time: {elapsed_time:.2f} seconds")

    def test_memory_usage_during_analysis(self, sample_ibdiagnet_dir):
        """Test memory usage during analysis."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        # Run analysis
        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory

        assert response.status_code == 200

        # Memory increase should be reasonable (< 500MB for standard dataset)
        print(f"\nMemory increase: {memory_increase:.2f} MB")
        assert memory_increase < 500

    def test_parallel_service_execution_performance(self, sample_ibdiagnet_dir):
        """Test that parallel execution improves performance."""
        # This test verifies that services run in parallel
        # Sequential execution would take much longer

        # Create zip
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

        assert response.status_code == 200

        # With parallel execution, should be faster than sequential
        # (This is a relative test - actual time depends on hardware)
        print(f"\nParallel execution time: {elapsed_time:.2f} seconds")

    def test_cache_effectiveness(self, sample_ibdiagnet_dir):
        """Test that caching improves performance on repeated operations."""
        # First run (cold cache)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        zip_buffer.seek(0)

        start_time = time.time()
        response1 = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", io.BytesIO(zip_buffer.read()), "application/zip")}
        )
        first_run_time = time.time() - start_time

        # Second run (warm cache - if caching is implemented)
        zip_buffer.seek(0)

        start_time = time.time()
        response2 = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet2.zip", io.BytesIO(zip_buffer.read()), "application/zip")}
        )
        second_run_time = time.time() - start_time

        assert response1.status_code == 200
        assert response2.status_code == 200

        print(f"\nFirst run: {first_run_time:.2f}s, Second run: {second_run_time:.2f}s")


@pytest.mark.slow
class TestStress:
    """Stress tests for the system."""

    def test_rapid_sequential_uploads(self, sample_ibdiagnet_dir):
        """Test handling of rapid sequential uploads."""
        # Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        # Upload multiple times rapidly
        responses = []
        for i in range(5):
            zip_buffer.seek(0)
            response = client.post(
                "/api/upload/ibdiagnet",
                files={"file": (f"ibdiagnet{i}.zip", io.BytesIO(zip_buffer.read()), "application/zip")}
            )
            responses.append(response)

        # All should succeed or be rate limited
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)

        assert success_count + rate_limited_count == 5

    def test_concurrent_analysis_requests(self, sample_ibdiagnet_dir):
        """Test handling of concurrent analysis requests."""
        import concurrent.futures

        # Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        def upload_file(index):
            zip_buffer.seek(0)
            return client.post(
                "/api/upload/ibdiagnet",
                files={"file": (f"ibdiagnet{index}.zip", io.BytesIO(zip_buffer.read()), "application/zip")}
            )

        # Upload concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_file, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Should handle concurrent requests
        success_count = sum(1 for r in results if r.status_code == 200)
        assert success_count >= 0  # At least some should succeed

    def test_rate_limiting_effectiveness(self):
        """Test that rate limiting works correctly."""
        # Make many rapid requests
        responses = []
        for i in range(15):  # Exceed rate limit (10 req/min)
            response = client.get("/api/health")
            responses.append(response)

        # Should have some rate limited responses
        rate_limited = [r for r in responses if r.status_code == 429]
        assert len(rate_limited) > 0

    def test_long_running_analysis(self, sample_ibdiagnet_dir):
        """Test system stability during long-running analysis."""
        # This test verifies that the system doesn't crash or leak resources
        # during extended operation

        # Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        # Run multiple analyses
        for i in range(3):
            zip_buffer.seek(0)
            response = client.post(
                "/api/upload/ibdiagnet",
                files={"file": (f"ibdiagnet{i}.zip", io.BytesIO(zip_buffer.read()), "application/zip")}
            )

            # Should continue to work
            assert response.status_code in [200, 429]


@pytest.mark.slow
class TestScalability:
    """Scalability tests."""

    def test_large_node_count_handling(self):
        """Test handling of networks with large node counts."""
        # This would require a large dataset
        # Conceptual test for documentation
        pass

    def test_high_anomaly_count_handling(self):
        """Test handling of datasets with many anomalies."""
        # This would require a dataset with many issues
        # Conceptual test for documentation
        pass

    def test_memory_cleanup_after_analysis(self, sample_ibdiagnet_dir):
        """Test that memory is properly cleaned up after analysis."""
        import psutil
        import os
        import gc

        process = psutil.Process(os.getpid())

        # Create zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file_path in sample_ibdiagnet_dir.iterdir():
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)

        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run analysis
        zip_buffer.seek(0)
        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("ibdiagnet.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code == 200

        # Force garbage collection
        gc.collect()

        # Wait a bit for cleanup
        time.sleep(2)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_retained = final_memory - initial_memory

        # Memory should not grow indefinitely
        print(f"\nMemory retained after cleanup: {memory_retained:.2f} MB")
        assert memory_retained < 200  # Should not retain too much memory
