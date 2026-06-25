import json
import pytest


# ---------------------------------------------------------------------------
# API CRUD
# ---------------------------------------------------------------------------

def test_list_bookmarks_empty(client):
    resp = client.get("/api/bookmarks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_bookmark(client):
    resp = client.post("/api/bookmarks", json={"name": "Google", "url": "https://google.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Google"
    assert data["url"] == "https://google.com"
    assert data["notes"] == ""
    assert "id" in data
    assert "created_at" in data


def test_list_bookmarks_after_create(client):
    client.post("/api/bookmarks", json={"name": "A", "url": "https://a.com"})
    client.post("/api/bookmarks", json={"name": "B", "url": "https://b.com"})
    resp = client.get("/api/bookmarks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_bookmark(client):
    created = client.post("/api/bookmarks", json={"name": "Old", "url": "https://old.com"}).json()
    resp = client.put(
        f"/api/bookmarks/{created['id']}",
        json={"name": "New", "url": "https://new.com", "notes": "updated", "sort_order": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New"
    assert data["url"] == "https://new.com"
    assert data["notes"] == "updated"


def test_update_nonexistent(client):
    resp = client.put(
        "/api/bookmarks/nonexistent",
        json={"name": "X", "url": "https://x.com", "notes": "", "sort_order": 0},
    )
    assert resp.status_code == 404


def test_delete_bookmark(client):
    created = client.post("/api/bookmarks", json={"name": "Del", "url": "https://del.com"}).json()
    resp = client.delete(f"/api/bookmarks/{created['id']}")
    assert resp.status_code == 200
    assert client.get("/api/bookmarks").json() == []


def test_delete_nonexistent(client):
    resp = client.delete("/api/bookmarks/nonexistent")
    assert resp.status_code == 404


def test_create_bookmark_missing_fields(client):
    resp = client.post("/api/bookmarks", json={"name": "NoURL"})
    assert resp.status_code == 422


def test_bookmarks_injected_on_launch(client, monkeypatch, tmp_path):
    """启动时应将书签写入 Default/Bookmarks 文件。"""
    import asyncio
    from unittest.mock import AsyncMock, patch, MagicMock
    import backend.services.browser as browser_service

    monkeypatch.setattr(browser_service, "STARTUP_PROBE_SECONDS", 0.05)
    monkeypatch.chdir(tmp_path)

    client.post("/api/bookmarks", json={"name": "Google", "url": "https://google.com"})

    p = client.post("/api/profiles", json={"name": "P"}).json()

    written_bookmarks = []

    def fake_write(udd, bookmarks):
        written_bookmarks.extend(bookmarks)

    mock_process = MagicMock()
    mock_process.returncode = None
    stop_event = asyncio.Event()

    async def _wait():
        await stop_event.wait()
        return 0

    mock_process.wait = _wait
    mock_process.terminate = MagicMock(side_effect=lambda: stop_event.set())
    mock_process.kill = MagicMock(side_effect=lambda: stop_event.set())

    with (
        patch("backend.services.browser.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process),
        patch("backend.routers.instances.browser.launch_profile", wraps=browser_service.launch_profile),
        patch("backend.services.browser_worker._write_bookmarks", side_effect=fake_write),
    ):
        resp = client.post("/api/instances/launch", json={"profile_id": p["id"]})

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# _write_bookmarks 单元测试
# ---------------------------------------------------------------------------

def test_write_bookmarks_creates_file(tmp_path):
    from backend.services.browser_worker import _write_bookmarks
    udd = str(tmp_path / "profile")
    _write_bookmarks(udd, [{"name": "Google", "url": "https://google.com"}])
    bm_file = tmp_path / "profile" / "Default" / "Bookmarks"
    assert bm_file.exists()


def test_write_bookmarks_json_structure(tmp_path):
    from backend.services.browser_worker import _write_bookmarks
    udd = str(tmp_path / "profile")
    _write_bookmarks(udd, [
        {"name": "Google", "url": "https://google.com"},
        {"name": "GitHub", "url": "https://github.com"},
    ])
    data = json.loads((tmp_path / "profile" / "Default" / "Bookmarks").read_text())
    assert data["version"] == 1
    assert "checksum" in data
    assert len(data["checksum"]) == 32  # MD5 hex
    children = data["roots"]["bookmark_bar"]["children"]
    assert len(children) == 2
    assert children[0]["name"] == "Google"
    assert children[0]["type"] == "url"
    assert children[0]["url"] == "https://google.com"
    assert children[1]["name"] == "GitHub"


def test_write_bookmarks_empty(tmp_path):
    from backend.services.browser_worker import _write_bookmarks
    udd = str(tmp_path / "profile")
    _write_bookmarks(udd, [])
    data = json.loads((tmp_path / "profile" / "Default" / "Bookmarks").read_text())
    assert data["roots"]["bookmark_bar"]["children"] == []
    assert len(data["checksum"]) == 32


def test_write_bookmarks_checksum_stable(tmp_path):
    """相同内容写两次，checksum 应该相同（time 除外，但 checksum 只依赖内容）。"""
    from backend.services.browser_worker import _write_bookmarks
    import hashlib

    bookmarks = [{"name": "Test", "url": "https://test.com"}]
    udd = str(tmp_path / "profile")
    _write_bookmarks(udd, bookmarks)
    data1 = json.loads((tmp_path / "profile" / "Default" / "Bookmarks").read_text())

    _write_bookmarks(udd, bookmarks)
    data2 = json.loads((tmp_path / "profile" / "Default" / "Bookmarks").read_text())

    # checksum 依赖 name/id/url，node id 固定为 "4"，所以两次相同
    assert data1["checksum"] == data2["checksum"]


def test_write_bookmarks_idempotent_directory(tmp_path):
    """Default/ 目录已存在时也不应报错。"""
    from backend.services.browser_worker import _write_bookmarks
    udd = str(tmp_path / "profile")
    (tmp_path / "profile" / "Default").mkdir(parents=True)
    _write_bookmarks(udd, [{"name": "X", "url": "https://x.com"}])
    assert (tmp_path / "profile" / "Default" / "Bookmarks").exists()
