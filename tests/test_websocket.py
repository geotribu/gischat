from typing import Any

import pytest
from fastapi.testclient import TestClient

from gischat import INTERNAL_MESSAGE_AUTHOR
from tests.conftest import test_rooms

TEST_MESSAGE = "Is this websocket working ?"


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_connection(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        data = websocket.receive_json()
        assert data == {"author": INTERNAL_MESSAGE_AUTHOR, "nb_users": 1}


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_put_message(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        assert websocket.receive_json() == {
            "author": INTERNAL_MESSAGE_AUTHOR,
            "nb_users": 1,
        }
        client.put(
            f"/room/{room}/message",
            json={
                "message": TEST_MESSAGE,
                "author": f"ws-tester-{room}",
                "avatar": "postgis",
            },
        )
        data = websocket.receive_json()
        assert data == {
            "message": TEST_MESSAGE,
            "author": f"ws-tester-{room}",
            "avatar": "postgis",
        }


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_send_message(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        assert websocket.receive_json() == {
            "author": INTERNAL_MESSAGE_AUTHOR,
            "nb_users": 1,
        }
        websocket.send_json({"message": TEST_MESSAGE, "author": f"ws-tester-{room}"})
        data = websocket.receive_json()
        assert data == {
            "message": TEST_MESSAGE,
            "author": f"ws-tester-{room}",
            "avatar": None,
        }


def nb_connected_users(json: dict[str, Any], room: str) -> bool:
    """
    Utils function to get number of connected users in a room from a status dict
    """
    rooms_dict = {r["name"]: r["nb_connected_users"] for r in json["rooms"]}
    return rooms_dict[room]


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_nb_users_connected(client: TestClient, room: str):
    assert nb_connected_users(client.get("/status").json(), room) == 0
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:
        assert websocket1.receive_json() == {
            "author": INTERNAL_MESSAGE_AUTHOR,
            "nb_users": 1,
        }
        assert nb_connected_users(client.get("/status").json(), room) == 1
        with client.websocket_connect(f"/room/{room}/ws") as websocket2:
            assert websocket1.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "nb_users": 2,
            }
            assert websocket2.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "nb_users": 2,
            }
            assert nb_connected_users(client.get("/status").json(), room) == 2
        assert websocket1.receive_json() == {
            "author": INTERNAL_MESSAGE_AUTHOR,
            "nb_users": 1,
        }
        assert nb_connected_users(client.get("/status").json(), room) == 1
    assert nb_connected_users(client.get("/status").json(), room) == 0


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_uncompliant_message(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:
        assert websocket1.receive_json() == {
            "author": INTERNAL_MESSAGE_AUTHOR,
            "nb_users": 1,
        }
        websocket1.send_json({"message": TEST_MESSAGE, "author": "chri$tian"})
        with client.websocket_connect(f"/room/{room}/ws"):
            assert websocket1.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "nb_users": 2,
            }


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_send_newcomer(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        websocket.send_json({"author": INTERNAL_MESSAGE_AUTHOR, "newcomer": "Isidore"})
        assert websocket.receive_json() == {
            "author": INTERNAL_MESSAGE_AUTHOR,
            "nb_users": 1,
        }
        assert websocket.receive_json() == {
            "author": INTERNAL_MESSAGE_AUTHOR,
            "newcomer": "Isidore",
        }


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_send_newcomer_multiple(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:
        websocket1.send_json({"author": INTERNAL_MESSAGE_AUTHOR, "newcomer": "user1"})
        with client.websocket_connect(f"/room/{room}/ws") as websocket2:
            websocket2.send_json(
                {"author": INTERNAL_MESSAGE_AUTHOR, "newcomer": "user2"}
            )
            assert websocket1.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "nb_users": 1,
            }
            assert websocket1.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "newcomer": "user1",
            }
            assert websocket1.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "nb_users": 2,
            }
            assert websocket1.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "newcomer": "user2",
            }
            assert websocket2.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "nb_users": 2,
            }
            assert websocket2.receive_json() == {
                "author": INTERNAL_MESSAGE_AUTHOR,
                "newcomer": "user2",
            }


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_send_newcomer_api_call(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:
        websocket1.send_json({"author": INTERNAL_MESSAGE_AUTHOR, "newcomer": "Isidore"})
        assert client.get(f"/room/{room}/users").json() == ["Isidore"]
        with client.websocket_connect(f"/room/{room}/ws") as websocket2:
            websocket2.send_json(
                {"author": INTERNAL_MESSAGE_AUTHOR, "newcomer": "Barnabe"}
            )
            assert client.get(f"/room/{room}/users").json() == ["Barnabe", "Isidore"]
