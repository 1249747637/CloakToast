def test_create_profile(client):
    resp = client.post("/api/profiles", json={"name": "Test Profile"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Profile"
    assert "id" in data
    assert data["is_running"] is False


def test_list_profiles(client):
    client.post("/api/profiles", json={"name": "P1"})
    client.post("/api/profiles", json={"name": "P2"})
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_profile(client):
    created = client.post("/api/profiles", json={"name": "P"}).json()
    resp = client.get(f"/api/profiles/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "P"


def test_update_profile(client):
    created = client.post("/api/profiles", json={"name": "Old"}).json()
    resp = client.put(f"/api/profiles/{created['id']}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


def test_delete_profile(client):
    created = client.post("/api/profiles", json={"name": "Del"}).json()
    resp = client.delete(f"/api/profiles/{created['id']}")
    assert resp.status_code == 200
    assert client.get(f"/api/profiles/{created['id']}").status_code == 404


def test_duplicate_profile(client):
    created = client.post("/api/profiles", json={"name": "Original"}).json()
    resp = client.post(f"/api/profiles/{created['id']}/duplicate")
    assert resp.status_code == 200
    dup = resp.json()
    assert dup["name"] == "Original (副本)"
    assert dup["id"] != created["id"]
