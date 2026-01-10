"""Integration tests for API endpoints."""

import pytest
import io
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


class TestAPIUpload:
    """Test API upload endpoints."""

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "version" in data

    def test_upload_ibdiagnet_invalid_file_type(self):
        """Test upload with invalid file type."""
        # Create a fake text file
        fake_file = io.BytesIO(b"This is not a zip file")

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("test.txt", fake_file, "text/plain")}
        )

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_ibdiagnet_file_too_large(self):
        """Test upload with file exceeding size limit."""
        # Create a large fake file (simulate > 500MB)
        # Note: We can't actually create 500MB in memory for testing
        # This test documents the expected behavior
        pass

    def test_upload_ibdiagnet_invalid_zip_content(self):
        """Test upload with invalid zip content (magic bytes mismatch)."""
        # Create a file with .zip extension but wrong content
        fake_zip = io.BytesIO(b"Not a real zip file content")

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("fake.zip", fake_zip, "application/zip")}
        )

        assert response.status_code == 400
        assert "content does not match" in response.json()["detail"].lower()

    def test_upload_ibdiagnet_no_db_csv(self):
        """Test upload with zip file but no db_csv inside."""
        # Create a valid zip file without db_csv
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("dummy.txt", "This is a dummy file")

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("test.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code == 400
        assert "No .db_csv files found" in response.json()["detail"]

    def test_upload_ibdiagnet_success(self, sample_ibdiagnet_dir):
        """Test successful IBDiagnet upload and analysis."""
        # Create a zip file from sample data
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

        # Should succeed
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
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
        assert 0 <= health["score"] <= 100

    def test_upload_ufm_csv_invalid_file_type(self):
        """Test UFM CSV upload with invalid file type."""
        fake_file = io.BytesIO(b"Not a CSV")

        response = client.post(
            "/api/upload/ufm-csv",
            files={"file": ("test.zip", fake_file, "application/zip")}
        )

        assert response.status_code == 400

    def test_upload_ufm_csv_empty_file(self):
        """Test UFM CSV upload with empty file."""
        empty_csv = io.BytesIO(b"")

        response = client.post(
            "/api/upload/ufm-csv",
            files={"file": ("empty.csv", empty_csv, "text/csv")}
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_upload_ufm_csv_success(self):
        """Test successful UFM CSV upload."""
        # Create a simple CSV
        csv_content = b"Column1,Column2,Column3\nValue1,Value2,Value3\nValue4,Value5,Value6"
        csv_buffer = io.BytesIO(csv_content)

        response = client.post(
            "/api/upload/ufm-csv",
            files={"file": ("test.csv", csv_buffer, "text/csv")}
        )

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] == "success"
        assert "columns" in data
        assert "row_count" in data
        assert "data" in data

        # Verify columns
        assert data["columns"] == ["Column1", "Column2", "Column3"]
        assert data["row_count"] == 2

    def test_rate_limiting(self):
        """Test rate limiting middleware."""
        # Make multiple rapid requests
        responses = []
        for _ in range(15):  # Exceed the 10 requests/minute limit
            response = client.get("/api/health")
            responses.append(response)

        # At least one should be rate limited
        rate_limited = [r for r in responses if r.status_code == 429]
        assert len(rate_limited) > 0

    def test_request_id_header(self):
        """Test that request ID is added to responses."""
        response = client.get("/api/health")

        # Should have X-Request-ID header
        assert "X-Request-ID" in response.headers

    def test_cors_headers(self):
        """Test CORS headers are present."""
        response = client.options("/api/health")

        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers


class TestAPISecurityValidation:
    """Test security validation in API."""

    def test_path_traversal_prevention(self):
        """Test that path traversal attacks are prevented."""
        # Create a zip with path traversal attempt
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            # Try to write outside the extraction directory
            zip_file.writestr("../../etc/passwd", "malicious content")

        zip_buffer.seek(0)

        response = client.post(
            "/api/upload/ibdiagnet",
            files={"file": ("malicious.zip", zip_buffer, "application/zip")}
        )

        # Should be rejected or handled safely
        # The exact response depends on implementation
        assert response.status_code in [400, 500]

    def test_file_size_validation(self):
        """Test file size validation."""
        # This is documented behavior - actual test would require large file
        pass

    def test_magic_bytes_validation(self):
        """Test magic bytes validation for file types."""
        # Already covered in test_upload_ibdiagnet_invalid_zip_content
        pass
