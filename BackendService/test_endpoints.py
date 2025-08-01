import pytest
from fastapi import status
from httpx import AsyncClient
from main import app

# Set up with pytest-asyncio, httpx.AsyncClient, and FastAPI test app

@pytest.mark.asyncio
async def test_token_success():
    """
    Test /auth/token endpoint: valid credentials should return access token.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/auth/token", data={"username": "user1", "password": "password"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_token_failure():
    """
    Test /auth/token endpoint: invalid credentials should return 401 error.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/auth/token", data={"username": "user1", "password": "wrongpass"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.json()["detail"] == "Incorrect username or password"

@pytest.mark.asyncio
async def test_health_check():
    """
    Test /subtitles/health endpoint for healthy response.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/subtitles/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_generate_subtitles_success(monkeypatch):
    """
    Test /subtitles/generate-subtitles endpoint for success with mocked LLM call.
    """
    payload = {"video_path": "/fake/path/video.mp4", "language": "English"}

    # Patch LLM function to avoid real call
    from subtitle_processor import generate_subtitles_with_llm

    def fake_generate_subtitles_with_llm(video_path, language):
        assert video_path == payload["video_path"]
        assert language == payload["language"]
        return "1\n00:00:00,000 --> 00:00:10,000\nFake subtitle"

    monkeypatch.setattr("subtitle_processor.generate_subtitles_with_llm", fake_generate_subtitles_with_llm)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/subtitles/generate-subtitles", json=payload)
    assert resp.status_code == 200
    assert "subtitles" in resp.json()
    assert resp.json()["subtitles"].startswith("1")

@pytest.mark.asyncio
async def test_generate_subtitles_error(monkeypatch):
    """
    Test /subtitles/generate-subtitles endpoint for internal server error case.
    """
    payload = {"video_path": "/fake/path/video.mp4", "language": "English"}

    def fake_generate_subtitles_with_llm(video_path, language):
        raise Exception("LLM error")

    monkeypatch.setattr("subtitle_processor.generate_subtitles_with_llm", fake_generate_subtitles_with_llm)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/subtitles/generate-subtitles", json=payload)
    assert resp.status_code == 500
    assert "Subtitle generation failed" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_translate_subtitles_success(monkeypatch):
    """
    Test /subtitles/translate-subtitles endpoint for success with mocked LLM call.
    """
    payload = {"subtitle_text": "1\n00:00:00,000 --> 00:00:10,000\nHello", "target_language": "French"}

    def fake_translate_subtitles_with_llm(subtitle_text, target_language):
        assert subtitle_text == payload["subtitle_text"]
        assert target_language == payload["target_language"]
        return "1\n00:00:00,000 --> 00:00:10,000\nBonjour"

    monkeypatch.setattr("subtitle_processor.translate_subtitles_with_llm", fake_translate_subtitles_with_llm)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/subtitles/translate-subtitles", json=payload)
    assert resp.status_code == 200
    assert "subtitles" in resp.json()
    assert resp.json()["subtitles"].startswith("1")

@pytest.mark.asyncio
async def test_translate_subtitles_error(monkeypatch):
    """
    Test /subtitles/translate-subtitles endpoint for failure/exception.
    """
    payload = {"subtitle_text": "1\n00:00:00,000 --> 00:00:10,000\nHello", "target_language": "German"}

    def fake_translate_subtitles_with_llm(subtitle_text, target_language):
        raise Exception("LLM translation failed!")

    monkeypatch.setattr("subtitle_processor.translate_subtitles_with_llm", fake_translate_subtitles_with_llm)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/subtitles/translate-subtitles", json=payload)
    assert resp.status_code == 500
    assert "Subtitle translation failed" in resp.json()["detail"]

# Instructions for running:
"""
To run these backend tests:

1. Install dependencies if not present:
   pip install pytest pytest-asyncio httpx

2. From the Subtitle_Sync_Platform/BackendService folder run:
   pytest --maxfail=2 -v

   (or, for more concise output: pytest)

By default, LLM-dependent endpoints are fully mocked; no real API keys or LLM calls are made.
"""
