import pytest
from fastapi.testclient import TestClient

from gischat.utils import get_poetry_version
from tests.conftest import test_rooms


def test_version(client: TestClient):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["version"] == get_poetry_version()


@pytest.mark.parametrize("room", test_rooms())
def test_status(client: TestClient, room: str):
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["healthy"]
    assert "rooms" in data
    rooms = [r["name"] for r in data["rooms"]]
    assert room in rooms
    for r in data["rooms"]:
        assert r["nb_connected_users"] == 0


@pytest.mark.parametrize("room", test_rooms())
def test_rooms(client: TestClient, room: str):
    response = client.get("/rooms")
    assert response.status_code == 200
    assert room in response.json()
