import os
import sys
from pathlib import Path

os.environ.setdefault("USE_SQLITE_FALLBACK", "True")
os.environ.setdefault("CELERY_ENABLED", "False")
os.environ.setdefault("DJANGO_DEBUG", "True")

import pytest
from django.core.management import call_command
from fastapi.testclient import TestClient
from rest_framework.test import APIClient

# Make ai_service importable so integration tests invoke the real FastAPI pipeline
AI_SERVICE_DIR = str(Path(__file__).resolve().parents[4] / "ai_service")
if AI_SERVICE_DIR not in sys.path:
    sys.path.insert(0, AI_SERVICE_DIR)

from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def seeded_db(db):
    call_command("seed_demo_data")
    return True


@pytest.fixture
def bridge_real_ai_service(monkeypatch):
    """
    Route backend httpx calls to the real in-process FastAPI AI Service TestClient
    so integration tests verify genuine TF-IDF/SVD + Cosine + DBSCAN + Scoring execution.
    """
    test_client = TestClient(fastapi_app)

    class _MockResponse:
        def __init__(self, resp):
            self._resp = resp
            self.status_code = resp.status_code

        def raise_for_status(self):
            if self._resp.status_code >= 400:
                raise RuntimeError(f"AI service HTTP {self._resp.status_code}: {self._resp.text}")

        def json(self):
            return self._resp.json()

    class _InProcessHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):
            path = "/" + url.split("/", 3)[-1]
            return _MockResponse(test_client.post(path, json=json, headers=headers or {}))

    monkeypatch.setattr("apps.insights.services.httpx.Client", _InProcessHttpxClient)
    monkeypatch.setattr("apps.feedbacks.views.httpx.Client", _InProcessHttpxClient)
    return test_client
