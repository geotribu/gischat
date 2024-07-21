import pytest
from fastapi.testclient import TestClient

from gischat.utils import get_poetry_version
from tests import TEST_RULES
from tests.conftest import test_rooms


def test_get_version(client: TestClient):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["version"] == get_poetry_version()


@pytest.mark.parametrize("room", test_rooms())
def test_get_status(client: TestClient, room: str):
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
def test_get_rooms(client: TestClient, room: str):
    response = client.get("/rooms")
    assert response.status_code == 200
    assert room in response.json()


def test_get_rules(client: TestClient):
    response = client.get("/rules")
    assert response.status_code == 200
    assert response.json()["rules"] == TEST_RULES


@pytest.mark.parametrize("room", test_rooms())
def test_put_message(client: TestClient, room: str):
    response = client.put(
        f"/room/{room}/message",
        json={"message": "fromage", "author": f"ws-tester-{room}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "fromage"
    assert response.json()["author"] == f"ws-tester-{room}"


def test_put_message_wrong_room(client: TestClient):
    assert (
        client.put(
            "/room/fromage/message", json={"message": "fromage", "author": "ws-tester"}
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/room/void/message", json={"message": "fromage", "author": "ws-tester"}
        ).status_code
        == 404
    )
