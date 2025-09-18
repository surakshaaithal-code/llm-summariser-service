from typing import Any, Dict, Optional
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_redis


class FakeRedis:
    def __init__(self) -> None:
        self.last_hset_args: Optional[Dict[str, Any]] = None

    async def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        self.last_hset_args = {"key": key, "mapping": mapping}
        return 1

    async def aclose(self) -> None:
        return None


@pytest.fixture()
def client():
    fake = FakeRedis()

    async def override_get_redis():
        yield fake

    app.dependency_overrides[get_redis] = override_get_redis
    with TestClient(app) as c:
        yield c, fake
    app.dependency_overrides.pop(get_redis, None)


def test_create_document_success(client):
    c, fake = client
    payload = {"name": "Example Doc", "URL": "https://example.com"}

    resp = c.post("/documents/", json=payload)

    assert resp.status_code == 202
    data = resp.json()

    assert set(data.keys()) == {"document_uuid", "status", "name", "URL", "summary"}
    assert data["status"] == "PENDING"
    assert data["name"] == payload["name"]
    expected_url = payload["URL"] if payload["URL"].endswith("/") else payload["URL"] + "/"
    assert data["URL"] == expected_url
    assert data["summary"] is None

    # validate UUID format (basic check: contains 4 dashes and hex chars length)
   # strict UUID validation
    assert uuid.UUID(data["document_uuid"])
    # ensure Redis hset was called with expected values
    assert fake.last_hset_args is not None
    assert fake.last_hset_args["key"].startswith("document:")
    stored = fake.last_hset_args["mapping"]
    assert stored["status"] == "PENDING"
    assert stored["name"] == payload["name"]
    assert stored["URL"] == expected_url
    assert stored["summary"] == ""
    
def test_create_document_validation_error(client):
    c, _ = client
    # invalid URL
    payload = {"name": "Example Doc", "URL": "not-a-url"}
    resp = c.post("/documents/", json=payload)
    assert resp.status_code == 422

