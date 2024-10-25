import pytest
from fastapi.testclient import TestClient

from gischat.utils import get_poetry_version
from tests import MAX_AUTHOR_LENGTH, MAX_MESSAGE_LENGTH, MIN_AUTHOR_LENGTH, TEST_RULES
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
    assert response.json()["main_lang"] == "en"
    assert response.json()["min_author_length"] == int(MIN_AUTHOR_LENGTH)
    assert response.json()["max_author_length"] == int(MAX_AUTHOR_LENGTH)
    assert response.json()["max_message_length"] == int(MAX_MESSAGE_LENGTH)


@pytest.mark.parametrize("room", test_rooms())
def test_get_users(client: TestClient, room: str):
    response = client.get(f"/room/{room}/users")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("room", test_rooms())
def test_put_message(client: TestClient, room: str):
    response = client.put(
        f"/room/{room}/message",
        json={"message": "fromage", "author": f"ws-tester-{room}", "avatar": "postgis"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "fromage"
    assert response.json()["author"] == f"ws-tester-{room}"
    assert response.json()["avatar"] == "postgis"


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


@pytest.mark.parametrize("room", test_rooms())
def test_put_message_author_not_alphanum(client: TestClient, room: str):
    response = client.put(
        f"/room/{room}/message",
        json={"message": "fromage", "author": "<darth_chri$tian>"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("room", test_rooms())
def test_put_message_author_too_short(client: TestClient, room: str):
    response = client.put(
        f"/room/{room}/message",
        json={"message": "fromage", "author": "ch", "avatar": "postgis"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("room", test_rooms())
def test_put_message_author_too_long(client: TestClient, room: str):
    author = "".join(["a" for _ in range(int(MAX_AUTHOR_LENGTH) + 1)])
    response = client.put(
        f"/room/{room}/message",
        json={"message": "fromage", "author": author},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("room", test_rooms())
def test_put_message_too_long(client: TestClient, room: str):
    message = "".join(["a" for _ in range(int(MAX_MESSAGE_LENGTH) + 1)])
    response = client.put(
        f"/room/{room}/message",
        json={"message": message, "author": "stephanie"},
    )
    assert response.status_code == 422
