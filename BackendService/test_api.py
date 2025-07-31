"""
API testing utilities and integration tests for the Subtitle Sync Platform
"""

import pytest
import asyncio
import os
import tempfile
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Import the main application
from main import app
from database import init_database, get_db_connection
from config import get_config

# Test client
client = TestClient(app)

class TestData:
    """Test data and utilities"""
    
    @staticmethod
    def create_test_srt_content() -> str:
        """Create sample SRT content for testing"""
        return """1
00:00:01,000 --> 00:00:05,000
This is the first subtitle line.
It can span multiple lines.

2
00:00:06,000 --> 00:00:10,000
This is the second subtitle.

3
00:00:11,000 --> 00:00:15,000
And this is the third subtitle line.
"""
    
    @staticmethod
    def create_test_webvtt_content() -> str:
        """Create sample WebVTT content for testing"""
        return """WEBVTT

1
00:00:01.000 --> 00:00:05.000
This is the first WebVTT cue.

2
00:00:06.000 --> 00:00:10.000
This is the second WebVTT cue.
"""
    
    @staticmethod
    def create_test_video_file() -> bytes:
        """Create mock video file content"""
        # This would be actual video content in a real test
        return b"MOCK_VIDEO_CONTENT_FOR_TESTING"

class TestHealthEndpoints:
    """Test health check and basic endpoints"""
    
    def test_root_endpoint(self):
        """Test root health check endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_docs_endpoint(self):
        """Test API documentation endpoint"""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_endpoint(self):
        """Test OpenAPI schema endpoint"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema

class TestFileUpload:
    """Test file upload endpoints"""
    
    def test_subtitle_upload_success(self):
        """Test successful subtitle upload"""
        srt_content = TestData.create_test_srt_content()
        
        files = {"file": ("test.srt", srt_content, "text/plain")}
        data = {"language": "en"}
        
        response = client.post("/subtitles/upload", files=files, data=data)
        assert response.status_code == 200
        
        result = response.json()
        assert "id" in result
        assert result["filename"] == "test.srt"
        assert result["language"] == "en"
        assert result["status"] == "uploaded"
    
    def test_subtitle_upload_invalid_format(self):
        """Test subtitle upload with invalid format"""
        invalid_content = "This is not a valid subtitle file"
        
        files = {"file": ("test.txt", invalid_content, "text/plain")}
        
        response = client.post("/subtitles/upload", files=files)
        assert response.status_code == 400
    
    def test_video_upload_success(self):
        """Test successful video upload"""
        mock_video = TestData.create_test_video_file()
        
        files = {"file": ("test.mp4", mock_video, "video/mp4")}
        data = {"language": "en"}
        
        with patch('magic.from_file', return_value='video/mp4'):
            response = client.post("/videos/upload", files=files, data=data)
            assert response.status_code == 200
            
            result = response.json()
            assert "id" in result
            assert result["filename"] == "test.mp4"

class TestSubtitleProcessing:
    """Test subtitle processing endpoints"""
    
    def test_subtitle_validation(self):
        """Test subtitle validation endpoint"""
        # First upload a subtitle
        srt_content = TestData.create_test_srt_content()
        files = {"file": ("test.srt", srt_content, "text/plain")}
        
        upload_response = client.post("/subtitles/upload", files=files)
        subtitle_id = upload_response.json()["id"]
        
        # Then validate it
        response = client.get(f"/subtitles/{subtitle_id}/validate")
        assert response.status_code == 200
        
        result = response.json()
        assert "is_valid" in result
        assert "issues" in result
        assert "character_count" in result
    
    def test_list_subtitles(self):
        """Test listing subtitles"""
        response = client.get("/subtitles")
        assert response.status_code == 200
        
        result = response.json()
        assert isinstance(result, list)

class TestJobProcessing:
    """Test job processing endpoints"""
    
    def test_start_correction_job(self):
        """Test starting a correction job"""
        # Upload video and subtitle first
        srt_content = TestData.create_test_srt_content()
        video_content = TestData.create_test_video_file()
        
        # Upload subtitle
        subtitle_files = {"file": ("test.srt", srt_content, "text/plain")}
        subtitle_response = client.post("/subtitles/upload", files=subtitle_files)
        subtitle_id = subtitle_response.json()["id"]
        
        # Upload video
        video_files = {"file": ("test.mp4", video_content, "video/mp4")}
        with patch('magic.from_file', return_value='video/mp4'):
            video_response = client.post("/videos/upload", files=video_files)
            video_id = video_response.json()["id"]
        
        # Start correction job
        job_data = {
            "video_id": video_id,
            "subtitle_id": subtitle_id
        }
        
        response = client.post("/jobs/correction", data=job_data)
        assert response.status_code == 200
        
        result = response.json()
        assert "id" in result
        assert result["job_type"] == "correction"
        assert result["status"] == "pending"
    
    def test_start_generation_job(self):
        """Test starting a generation job"""
        # Upload video first
        video_content = TestData.create_test_video_file()
        video_files = {"file": ("test.mp4", video_content, "video/mp4")}
        
        with patch('magic.from_file', return_value='video/mp4'):
            video_response = client.post("/videos/upload", files=video_files)
            video_id = video_response.json()["id"]
        
        # Start generation job
        job_data = {
            "video_id": video_id,
            "target_language": "en"
        }
        
        response = client.post("/jobs/generation", data=job_data)
        assert response.status_code == 200
        
        result = response.json()
        assert "id" in result
        assert result["job_type"] == "generation"
    
    def test_get_job_status(self):
        """Test getting job status"""
        # First create a job (using generation as example)
        video_content = TestData.create_test_video_file()
        video_files = {"file": ("test.mp4", video_content, "video/mp4")}
        
        with patch('magic.from_file', return_value='video/mp4'):
            video_response = client.post("/videos/upload", files=video_files)
            video_id = video_response.json()["id"]
        
        job_data = {"video_id": video_id}
        job_response = client.post("/jobs/generation", data=job_data)
        job_id = job_response.json()["id"]
        
        # Get job status
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        
        result = response.json()
        assert "id" in result
        assert "status" in result
        assert "job_type" in result
    
    def test_list_jobs(self):
        """Test listing jobs"""
        response = client.get("/jobs")
        assert response.status_code == 200
        
        result = response.json()
        assert isinstance(result, list)

class TestUserManagement:
    """Test user management endpoints"""
    
    def test_register_user(self):
        """Test user registration"""
        user_data = {
            "username": "testuser",
            "password": "testpassword123",
            "email": "test@example.com",
            "role": "user"
        }
        
        response = client.post("/users/register", json=user_data)
        assert response.status_code == 200
        
        result = response.json()
        assert "id" in result
        assert result["username"] == "testuser"
        assert result["role"] == "user"
    
    def test_get_current_user(self):
        """Test getting current user info"""
        response = client.get("/users/me")
        assert response.status_code == 200
        
        result = response.json()
        assert "id" in result
        assert "username" in result
        assert "role" in result

class TestAdminEndpoints:
    """Test admin endpoints"""
    
    def test_get_system_stats(self):
        """Test getting system statistics"""
        response = client.get("/admin/stats")
        # This might return 403 if not admin, but endpoint should exist
        assert response.status_code in [200, 403]
    
    def test_get_audit_logs(self):
        """Test getting audit logs"""
        response = client.get("/admin/audit-logs")
        # This might return 403 if not admin, but endpoint should exist
        assert response.status_code in [200, 403]

class TestWorkflowIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_correction_workflow(self):
        """Test complete subtitle correction workflow"""
        # 1. Upload video and subtitle
        srt_content = TestData.create_test_srt_content()
        video_content = TestData.create_test_video_file()
        
        subtitle_files = {"file": ("workflow_test.srt", srt_content, "text/plain")}
        subtitle_response = client.post("/subtitles/upload", files=subtitle_files)
        assert subtitle_response.status_code == 200
        subtitle_id = subtitle_response.json()["id"]
        
        video_files = {"file": ("workflow_test.mp4", video_content, "video/mp4")}
        with patch('magic.from_file', return_value='video/mp4'):
            video_response = client.post("/videos/upload", files=video_files)
            assert video_response.status_code == 200
            video_id = video_response.json()["id"]
        
        # 2. Validate subtitle
        validation_response = client.get(f"/subtitles/{subtitle_id}/validate")
        assert validation_response.status_code == 200
        
        # 3. Start correction job
        job_data = {
            "video_id": video_id,
            "subtitle_id": subtitle_id
        }
        job_response = client.post("/jobs/correction", data=job_data)
        assert job_response.status_code == 200
        job_id = job_response.json()["id"]
        
        # 4. Check job status
        status_response = client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        
        # 5. Wait a moment for processing (in real tests, would poll until complete)
        import time
        time.sleep(1)
        
        # 6. Check final status
        final_status = client.get(f"/jobs/{job_id}")
        assert final_status.status_code == 200
    
    def test_subtitle_generation_workflow(self):
        """Test complete subtitle generation workflow"""
        # 1. Upload video
        video_content = TestData.create_test_video_file()
        video_files = {"file": ("generation_test.mp4", video_content, "video/mp4")}
        
        with patch('magic.from_file', return_value='video/mp4'):
            video_response = client.post("/videos/upload", files=video_files)
            assert video_response.status_code == 200
            video_id = video_response.json()["id"]
        
        # 2. Start generation job
        job_data = {
            "video_id": video_id,
            "target_language": "en"
        }
        job_response = client.post("/jobs/generation", data=job_data)
        assert job_response.status_code == 200
        job_id = job_response.json()["id"]
        
        # 3. Monitor job progress
        status_response = client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        
        # 4. List all jobs to verify it appears
        jobs_response = client.get("/jobs")
        assert jobs_response.status_code == 200
        jobs = jobs_response.json()
        job_ids = [job["id"] for job in jobs]
        assert job_id in job_ids

# Utility functions for test setup
def setup_test_database():
    """Setup test database"""
    init_database()

def teardown_test_files():
    """Clean up test files"""
    config = get_config()
    
    # Clean up upload directory
    upload_dir = config.settings.upload_dir
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            if filename.startswith("test") or filename.startswith("workflow"):
                file_path = os.path.join(upload_dir, filename)
                try:
                    os.remove(file_path)
                except Exception:
                    pass
    
    # Clean up processed directory
    processed_dir = config.settings.processed_dir
    if os.path.exists(processed_dir):
        for filename in os.listdir(processed_dir):
            if filename.startswith("test") or filename.startswith("workflow"):
                file_path = os.path.join(processed_dir, filename)
                try:
                    os.remove(file_path)
                except Exception:
                    pass

# Test runner
if __name__ == "__main__":
    # Setup
    setup_test_database()
    
    try:
        # Run tests
        pytest.main([__file__, "-v"])
    finally:
        # Cleanup
        teardown_test_files()
