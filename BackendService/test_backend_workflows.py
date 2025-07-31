import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from main import app, JOB_FILES_DIR, ALLOWED_EXTENSIONS

# --- Utility fixtures and sample data ---

@pytest.fixture(scope="module")
def client():
    """Yield FastAPI test client for the backend."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def tmp_job_dir(monkeypatch):
    """Ensure a temp job output directory is used for each test run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("main.JOB_FILES_DIR", tmpdir)
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        yield tmpdir

def sample_subtitle_content(fmt=".srt"):
    """Return simple subtitle file content for supported formats."""
    if fmt == ".srt":
        return b"""1
00:00:00,000 --> 00:00:01,000
Hello!
"""
    elif fmt == ".vtt":
        return b"""WEBVTT

00:00:00.000 --> 00:00:01.000
Hello!
"""
    elif fmt == ".ass":
        return b"""[Script Info]
Title: Test
[Events]
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Hello!
"""
    else:
        return b"dummy"

# --- Main tests for job submission, polling, and download ---

def test_subtitle_correction_and_download(client, tmp_job_dir):
    """
    End-to-end: Submit subtitle file for correction, poll job status, trigger result download.
    """
    # Step 1: Upload subtitle file with .srt extension
    resp = client.post(
        "/jobs/submit",
        files={"subtitle_file": ("example.srt", sample_subtitle_content(".srt"), "text/plain")},
    )
    assert resp.status_code == 200
    jdata = resp.json()
    assert "job_id" in jdata and jdata["status"] == "queued"
    job_id = jdata["job_id"]

    # Step 2: Poll status until complete (simulate backend worker)
    for attempt in range(20):
        stat = client.get(f"/jobs/{job_id}/status")
        assert stat.status_code == 200
        status_data = stat.json()
        if status_data["status"] == "complete" and status_data["download_url"]:
            break
        time.sleep(0.2)
    else:
        pytest.fail("Job did not complete in time")

    download_url = status_data["download_url"]
    assert download_url and "token=" in download_url

    # Step 3: Download file using returned URL (simulate frontend behavior)
    # Parse the path/token
    from urllib.parse import urlparse, parse_qs
    u = urlparse(download_url)
    dl_path = u.path
    token = parse_qs(u.query).get("token", [None])[0]
    assert dl_path.endswith(f"/jobs/{job_id}/result")

    # Ensure download works and gives correct file type
    dl_resp = client.get(f"{dl_path}?token={token}")
    assert dl_resp.status_code == 200
    assert dl_resp.headers.get("content-disposition", "").startswith("attachment;")
    assert b"Hello!" in dl_resp.content

def test_generation_workflow_and_download(client, tmp_job_dir):
    """
    End-to-end: Simulate subtitle generation (really just uploads another format).
    """
    for fmt in [".vtt", ".ass"]:
        resp = client.post(
            "/jobs/submit",
            files={"subtitle_file": (f"example{fmt}", sample_subtitle_content(fmt), "text/plain")},
        )
        assert resp.status_code == 200
        jdata = resp.json()
        job_id = jdata["job_id"]

        # Wait for job complete
        for attempt in range(20):
            stat = client.get(f"/jobs/{job_id}/status")
            assert stat.status_code == 200
            status_data = stat.json()
            if status_data["status"] == "complete" and status_data["download_url"]:
                break
            time.sleep(0.2)
        else:
            pytest.fail(f"Job with {fmt} did not complete")

        download_url = status_data["download_url"]
        assert download_url
        from urllib.parse import urlparse, parse_qs
        u = urlparse(download_url)
        dl_path = u.path
        token = parse_qs(u.query).get("token", [None])[0]
        assert dl_path.endswith(f"/jobs/{job_id}/result")

        # Download result
        dl_resp = client.get(f"{dl_path}?token={token}")
        assert dl_resp.status_code == 200
        assert b"Hello!" in dl_resp.content or b"Title: Test" in dl_resp.content

def test_invalid_format_rejected(client):
    """
    Correction/generation fails for unsupported file extension.
    """
    resp = client.post(
        "/jobs/submit",
        files={"subtitle_file": ("bad.xyz", b"bad file contents", "text/plain")},
    )
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]

def test_download_token_protection(client, tmp_job_dir):
    """
    Downloads with wrong/absent token are forbidden.
    """
    # Submit using .srt
    resp = client.post(
        "/jobs/submit",
        files={"subtitle_file": ("ex.srt", sample_subtitle_content(".srt"), "text/plain")},
    )
    job_id = resp.json()["job_id"]
    for _ in range(20):
        stat = client.get(f"/jobs/{job_id}/status")
        if stat.json()["status"] == "complete" and stat.json()["download_url"]:
            break
        time.sleep(0.2)
    url = stat.json()["download_url"]
    from urllib.parse import urlparse, parse_qs
    u = urlparse(url)
    dl_path = u.path
    real_token = parse_qs(u.query).get("token", [None])[0]

    # Omit token
    no_token_resp = client.get(dl_path)
    assert no_token_resp.status_code == 403

    # Wrong token
    wrong_token = real_token + "x"
    wrong_token_resp = client.get(dl_path + f"?token={wrong_token}")
    assert wrong_token_resp.status_code == 403

def test_download_before_ready(client, tmp_job_dir):
    """
    Downloading before job is ready gives error.
    """
    resp = client.post(
        "/jobs/submit",
        files={"subtitle_file": ("wait.srt", sample_subtitle_content(), "text/plain")},
    )
    job_id = resp.json()["job_id"]
    # Try to download immediately (job still queued, not complete)
    # Find correct token by checking job context
    from main import JOBS
    token = JOBS[job_id]["download_token"]
    url = f"/jobs/{job_id}/result?token={token}"
    dl = client.get(url)
    assert dl.status_code == 400
    assert "not finished" in dl.json()["detail"]

def test_job_not_found_returns_404(client):
    """Nonexistent job returns 404 for status and download."""
    not_real = "doesnotexistid"
    s1 = client.get(f"/jobs/{not_real}/status")
    d1 = client.get(f"/jobs/{not_real}/result?token=abc")
    assert s1.status_code == 404
    assert d1.status_code == 404

# --- End of backend workflow tests ---
