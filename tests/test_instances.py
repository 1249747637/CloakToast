from unittest.mock import AsyncMock, patch, MagicMock
import backend.services.browser as browser_service
import pytest


@pytest.fixture(autouse=True)
def clear_running_instances():
    """Ensure running_instances is empty before and after each test."""
    browser_service.running_instances.clear()
    yield
    browser_service.running_instances.clear()


def test_get_instances_empty(client):
    resp = client.get("/api/instances")
    assert resp.status_code == 200
    assert resp.json() == []


def test_launch_unknown_profile(client):
    resp = client.post("/api/instances/launch", json={"profile_id": "nonexistent"})
    assert resp.status_code == 404


def test_stop_not_running(client):
    p = client.post("/api/profiles", json={"name": "P"}).json()
    resp = client.post(f"/api/instances/stop/{p['id']}")
    assert resp.status_code == 400


def test_launch_profile(client):
    p = client.post("/api/profiles", json={"name": "P"}).json()
    mock_process = MagicMock()
    mock_process.returncode = None
    with patch(
        "backend.services.browser.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_process,
    ):
        resp = client.post("/api/instances/launch", json={"profile_id": p["id"]})
    assert resp.status_code == 200
    instances = client.get("/api/instances").json()
    assert len(instances) == 1
    assert instances[0]["profile_id"] == p["id"]
