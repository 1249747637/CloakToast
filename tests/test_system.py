import json


def test_get_system_info(client):
    resp = client.get("/api/system/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "installed_version" in data
    assert "license_key" in data


def test_save_license(client, tmp_path, monkeypatch):
    import backend.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")
    resp = client.put("/api/system/license", json={"license_key": "TEST-KEY"})
    assert resp.status_code == 200
    assert cfg.get_license_key() == "TEST-KEY"
