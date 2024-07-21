from fastapi.testclient import TestClient

from gischat.app import app
from gischat.utils import get_poetry_version

client = TestClient(app)


def test_version():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["version"] == get_poetry_version()


def test_status():
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["healthy"]
    assert "rooms" in data
