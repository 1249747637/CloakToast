def test_create_task(client):
    resp = client.post("/api/tasks", json={"name": "Task A", "urls": ["https://a.com"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Task A"
    assert data["urls"] == ["https://a.com"]


def test_task_detail_with_profiles(client):
    task = client.post("/api/tasks", json={"name": "T"}).json()
    p1 = client.post("/api/profiles", json={"name": "P1"}).json()
    p2 = client.post("/api/profiles", json={"name": "P2"}).json()
    client.post(f"/api/tasks/{task['id']}/profiles", json={"profile_ids": [p1["id"], p2["id"]]})
    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["total_profiles"] == 2
    assert detail["done_count"] == 0


def test_update_profile_status(client):
    task = client.post("/api/tasks", json={"name": "T"}).json()
    p = client.post("/api/profiles", json={"name": "P"}).json()
    client.post(f"/api/tasks/{task['id']}/profiles", json={"profile_ids": [p["id"]]})
    client.patch(f"/api/tasks/{task['id']}/profiles/{p['id']}/status", json={"status": "done"})
    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["done_count"] == 1


def test_remove_profile_from_task(client):
    task = client.post("/api/tasks", json={"name": "T"}).json()
    p = client.post("/api/profiles", json={"name": "P"}).json()
    client.post(f"/api/tasks/{task['id']}/profiles", json={"profile_ids": [p["id"]]})
    client.delete(f"/api/tasks/{task['id']}/profiles/{p['id']}")
    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["total_profiles"] == 0


def test_delete_task(client):
    task = client.post("/api/tasks", json={"name": "T"}).json()
    client.delete(f"/api/tasks/{task['id']}")
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
