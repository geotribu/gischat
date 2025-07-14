from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from gischat.models import QChatMessageTypeEnum
from tests import (
    MAX_AUTHOR_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_STORED_MESSAGES,
    MIN_AUTHOR_LENGTH,
)
from tests.conftest import get_test_channels
from tests.test_utils import is_in_dicts, is_subdict

TEST_TEXT_MESSAGE = "Is this websocket working ?"


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_connection(client: TestClient, channel: str):

    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:
        data = websocket.receive_json()

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            data,
        )


def test_websocket_connection_wrong_channel(client: TestClient):

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/channel/fr0mage/ws") as websocket:
            websocket.receive_json()


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_put_message(client: TestClient, channel: str):

    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket.receive_json(),
        )

        client.put(
            f"/channel/{channel}/text",
            json={
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{channel}",
                "avatar": "postgis",
                "text": TEST_TEXT_MESSAGE,
            },
        )
        data = websocket.receive_json()

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{channel}",
                "avatar": "postgis",
                "text": TEST_TEXT_MESSAGE,
            },
            data,
        )


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_send_message(client: TestClient, channel: str):

    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket.receive_json(),
        )

        websocket.send_json(
            {
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{channel}",
                "text": TEST_TEXT_MESSAGE,
            }
        )
        data = websocket.receive_json()

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{channel}",
                "avatar": None,
                "text": TEST_TEXT_MESSAGE,
            },
            data,
        )


def nb_connected_users(json: dict[str, Any], channel: str) -> bool:
    """
    Utils function to get number of connected users in a channel from a status dict
    """
    channels_dict = {r["name"]: r["nb_connected_users"] for r in json["channels"]}
    return channels_dict[channel]


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_nb_users_connected(client: TestClient, channel: str):

    assert nb_connected_users(client.get("/status").json(), channel) == 0

    with client.websocket_connect(f"/channel/{channel}/ws") as websocket1:

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket1.receive_json(),
        )

        assert nb_connected_users(client.get("/status").json(), channel) == 1

        with client.websocket_connect(f"/channel/{channel}/ws") as websocket2:

            assert is_subdict(
                {
                    "type": QChatMessageTypeEnum.NB_USERS.value,
                    "nb_users": 2,
                },
                websocket1.receive_json(),
            )
            assert is_subdict(
                {
                    "type": QChatMessageTypeEnum.NB_USERS.value,
                    "nb_users": 2,
                },
                websocket2.receive_json(),
            )
            assert nb_connected_users(client.get("/status").json(), channel) == 2

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket1.receive_json(),
        )
        assert nb_connected_users(client.get("/status").json(), channel) == 1

    assert nb_connected_users(client.get("/status").json(), channel) == 0


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_send_uncompliant(client: TestClient, channel: str):

    with client.websocket_connect(f"/channel/{channel}/ws") as websocket1:

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket1.receive_json(),
        )

        # send author with unallowed chars
        websocket1.send_json(
            {
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": "chri$tian",
                "text": TEST_TEXT_MESSAGE,
            }
        )

        assert (
            websocket1.receive_json()["type"] == QChatMessageTypeEnum.UNCOMPLIANT.value
        )

        # send too short author
        websocket1.send_json(
            {
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": "".join(["a" for _ in range(int(MIN_AUTHOR_LENGTH) - 1)]),
                "text": TEST_TEXT_MESSAGE,
            }
        )

        assert (
            websocket1.receive_json()["type"] == QChatMessageTypeEnum.UNCOMPLIANT.value
        )

        # send too long author
        websocket1.send_json(
            {
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": "".join(["a" for _ in range(int(MAX_AUTHOR_LENGTH) + 1)]),
                "text": TEST_TEXT_MESSAGE,
            }
        )

        assert (
            websocket1.receive_json()["type"] == QChatMessageTypeEnum.UNCOMPLIANT.value
        )

        # send too long message
        websocket1.send_json(
            {
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": "Thierry_le_0uf",
                "text": "".join(["a" for _ in range(int(MAX_MESSAGE_LENGTH) + 1)]),
            }
        )

        assert (
            websocket1.receive_json()["type"] == QChatMessageTypeEnum.UNCOMPLIANT.value
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
            websocket1.receive_json()["type"] == QChatMessageTypeEnum.UNCOMPLIANT.value
        )


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_send_newcomer(client: TestClient, channel: str):
    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:
        websocket.send_json(
            {"type": QChatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket.receive_json(),
        )
        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NEWCOMER.value,
                "newcomer": "Isidore",
            },
            websocket.receive_json(),
        )


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_send_newcomer_twice(client: TestClient, channel: str):
    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:
        # Isidore sends first registration
        websocket.send_json(
            {"type": QChatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket.receive_json(),
        )
        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NEWCOMER.value,
                "newcomer": "Isidore",
            },
            websocket.receive_json(),
        )

        # Isidore sends second registration -> forbidden
        websocket.send_json(
            {"type": QChatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.UNCOMPLIANT.value,
                "reason": f"User 'Isidore' already registered in channel {channel}",
            },
            websocket.receive_json(),
        )


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_send_newcomer_api_call(client: TestClient, channel: str):
    with client.websocket_connect(f"/channel/{channel}/ws") as websocket1:
        websocket1.send_json(
            {"type": QChatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )

        assert client.get(f"/channel/{channel}/users").json() == ["Isidore"]

        with client.websocket_connect(f"/channel/{channel}/ws") as websocket2:
            websocket2.send_json(
                {"type": QChatMessageTypeEnum.NEWCOMER.value, "newcomer": "Barnabe"}
            )

            assert client.get(f"/channel/{channel}/users").json() == [
                "Barnabe",
                "Isidore",
            ]


@pytest.mark.parametrize("channel", get_test_channels())
def test_websocket_stored_message(client: TestClient, channel: str):

    # first we send some dummy messages to the websocket.
    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:
        websocket.send_json(
            {"type": QChatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket.receive_json(),
        )
        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NEWCOMER.value,
                "newcomer": "Isidore",
            },
            websocket.receive_json(),
        )

        for i in range(int(MAX_STORED_MESSAGES) * 2):
            websocket.send_json(
                {
                    "type": QChatMessageTypeEnum.TEXT.value,
                    "author": f"ws-tester-{channel}",
                    "avatar": "dog",
                    "text": str(i),
                }
            )

    # then we assert we receive only the last `MAX_STORED_MESSAGES` of them.
    received_messages = []
    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:

        for i in range(int(MAX_STORED_MESSAGES)):
            received_messages.append(websocket.receive_json())

        # we receive also a `NB_USERS` type message.
        received_messages.append(websocket.receive_json())

        for i in range(int(MAX_STORED_MESSAGES)):
            message = {
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{channel}",
                "avatar": "dog",
                "text": str(i + int(MAX_STORED_MESSAGES)),
            }

            assert is_in_dicts(message, received_messages)

        nb_users_message = {
            "type": QChatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }

        assert is_in_dicts(nb_users_message, received_messages)
