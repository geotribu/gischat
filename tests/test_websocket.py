from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from gischat.models import GischatMessageTypeEnum
from tests import (
    MAX_AUTHOR_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_STORED_MESSAGES,
    MIN_AUTHOR_LENGTH,
)
from tests.conftest import get_test_rooms

TEST_TEXT_MESSAGE = "Is this websocket working ?"


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_connection(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        data = websocket.receive_json()
        assert data == {"type": GischatMessageTypeEnum.NB_USERS.value, "nb_users": 1}


def test_websocket_connection_wrong_room(client: TestClient):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/room/fr0mage/ws") as websocket:
            websocket.receive_json()


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_put_message(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        client.put(
            f"/room/{room}/text",
            json={
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{room}",
                "avatar": "postgis",
                "text": TEST_TEXT_MESSAGE,
            },
        )
        data = websocket.receive_json()
        assert data == {
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": f"ws-tester-{room}",
            "avatar": "postgis",
            "text": TEST_TEXT_MESSAGE,
        }


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_send_message(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        websocket.send_json(
            {
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{room}",
                "text": TEST_TEXT_MESSAGE,
            }
        )
        data = websocket.receive_json()
        assert data == {
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": f"ws-tester-{room}",
            "avatar": None,
            "text": TEST_TEXT_MESSAGE,
        }


def nb_connected_users(json: dict[str, Any], room: str) -> bool:
    """
    Utils function to get number of connected users in a room from a status dict
    """
    rooms_dict = {r["name"]: r["nb_connected_users"] for r in json["rooms"]}
    return rooms_dict[room]


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_nb_users_connected(client: TestClient, room: str):
    assert nb_connected_users(client.get("/status").json(), room) == 0
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:
        assert websocket1.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        assert nb_connected_users(client.get("/status").json(), room) == 1
        with client.websocket_connect(f"/room/{room}/ws") as websocket2:
            assert websocket1.receive_json() == {
                "type": GischatMessageTypeEnum.NB_USERS.value,
                "nb_users": 2,
            }
            assert websocket2.receive_json() == {
                "type": GischatMessageTypeEnum.NB_USERS.value,
                "nb_users": 2,
            }
            assert nb_connected_users(client.get("/status").json(), room) == 2
        assert websocket1.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        assert nb_connected_users(client.get("/status").json(), room) == 1
    assert nb_connected_users(client.get("/status").json(), room) == 0


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_send_uncompliant(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:
        assert websocket1.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        # send author with unallowed chars
        websocket1.send_json(
            {
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": "chri$tian",
                "text": TEST_TEXT_MESSAGE,
            }
        )
        assert (
            websocket1.receive_json()["type"]
            == GischatMessageTypeEnum.UNCOMPLIANT.value
        )
        # send too short author
        websocket1.send_json(
            {
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": "".join(["a" for _ in range(int(MIN_AUTHOR_LENGTH) - 1)]),
                "text": TEST_TEXT_MESSAGE,
            }
        )
        assert (
            websocket1.receive_json()["type"]
            == GischatMessageTypeEnum.UNCOMPLIANT.value
        )
        # send too long author
        websocket1.send_json(
            {
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": "".join(["a" for _ in range(int(MAX_AUTHOR_LENGTH) + 1)]),
                "text": TEST_TEXT_MESSAGE,
            }
        )
        assert (
            websocket1.receive_json()["type"]
            == GischatMessageTypeEnum.UNCOMPLIANT.value
        )
        # send too long message
        websocket1.send_json(
            {
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": "Thierry_le_0uf",
                "text": "".join(["a" for _ in range(int(MAX_MESSAGE_LENGTH) + 1)]),
            }
        )
        assert (
            websocket1.receive_json()["type"]
            == GischatMessageTypeEnum.UNCOMPLIANT.value
        )
        # send unknown message type
        websocket1.send_json(
            {
                "type": "fr0mage",
                "author": "Thierry_le_0uf",
                "text": "cc",
            }
        )
        assert (
            websocket1.receive_json()["type"]
            == GischatMessageTypeEnum.UNCOMPLIANT.value
        )


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_send_newcomer(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        websocket.send_json(
            {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NEWCOMER.value,
            "newcomer": "Isidore",
        }


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_send_newcomer_twice(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        # Isidore sends first registration
        websocket.send_json(
            {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NEWCOMER.value,
            "newcomer": "Isidore",
        }
        # Isidore sends second registration -> forbidden
        websocket.send_json(
            {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.UNCOMPLIANT.value,
            "reason": f"User 'Isidore' already registered in room {room}",
        }


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_send_newcomer_multiple(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:
        websocket1.send_json(
            {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "user1"}
        )
        with client.websocket_connect(f"/room/{room}/ws") as websocket2:
            websocket2.send_json(
                {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "user2"}
            )
            assert websocket1.receive_json() == {
                "type": GischatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            }
            assert websocket1.receive_json() == {
                "type": GischatMessageTypeEnum.NEWCOMER.value,
                "newcomer": "user1",
            }
            assert websocket1.receive_json() == {
                "type": GischatMessageTypeEnum.NB_USERS.value,
                "nb_users": 2,
            }
            assert websocket1.receive_json() == {
                "type": GischatMessageTypeEnum.NEWCOMER.value,
                "newcomer": "user2",
            }
            assert websocket2.receive_json() == {
                "type": GischatMessageTypeEnum.NB_USERS.value,
                "nb_users": 2,
            }
            assert websocket2.receive_json() == {
                "type": GischatMessageTypeEnum.NEWCOMER.value,
                "newcomer": "user2",
            }
        assert websocket1.receive_json() == {
            "type": GischatMessageTypeEnum.EXITER.value,
            "exiter": "user2",
        }
        assert websocket1.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_send_newcomer_api_call(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:
        websocket1.send_json(
            {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )
        assert client.get(f"/room/{room}/users").json() == ["Isidore"]
        with client.websocket_connect(f"/room/{room}/ws") as websocket2:
            websocket2.send_json(
                {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "Barnabe"}
            )
            assert client.get(f"/room/{room}/users").json() == ["Barnabe", "Isidore"]


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_stored_message(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        websocket.send_json(
            {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NEWCOMER.value,
            "newcomer": "Isidore",
        }
        for i in range(int(MAX_STORED_MESSAGES) * 2):
            websocket.send_json(
                {
                    "type": GischatMessageTypeEnum.TEXT.value,
                    "author": f"ws-tester-{room}",
                    "avatar": "dog",
                    "text": str(i),
                }
            )
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        for i in range(int(MAX_STORED_MESSAGES)):
            assert websocket.receive_json() == {
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{room}",
                "avatar": "dog",
                "text": str(i + int(MAX_STORED_MESSAGES)),
            }
