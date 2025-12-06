import pytest
from fastapi.testclient import TestClient

from gischat.models import QChatMessageTypeEnum
from gischat.utils import get_uv_version
from tests import (
    MAX_AUTHOR_LENGTH,
    MAX_GEOJSON_FEATURES,
    MAX_IMAGE_SIZE,
    MAX_MESSAGE_LENGTH,
    MAX_STORED_MESSAGES,
    MIN_AUTHOR_LENGTH,
    TEST_RULES,
)
from tests.conftest import get_test_channels
from tests.test_utils import is_subdict


def test_get_version(client: TestClient):
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json()["version"] == get_uv_version()


@pytest.mark.parametrize("channel", get_test_channels())
def test_get_status(client: TestClient, channel: str):
    response = client.get("/status")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["healthy"]
    assert "channels" in data

    channels = [r["name"] for r in data["channels"]]

    assert channel in channels

    for r in data["channels"]:
        assert r["nb_connected_users"] == 0


@pytest.mark.parametrize("channel", get_test_channels())
def test_get_channels(client: TestClient, channel: str):
    response = client.get("/channels")

    assert response.status_code == 200
    assert channel in response.json()


def test_get_rules(client: TestClient):
    response = client.get("/rules")

    assert response.status_code == 200
    assert response.json()["rules"] == TEST_RULES
    assert response.json()["main_lang"] == "en"
    assert response.json()["min_author_length"] == int(MIN_AUTHOR_LENGTH)
    assert response.json()["max_author_length"] == int(MAX_AUTHOR_LENGTH)
    assert response.json()["max_message_length"] == int(MAX_MESSAGE_LENGTH)
    assert response.json()["max_image_size"] == int(MAX_IMAGE_SIZE)
    assert response.json()["max_geojson_features"] == int(MAX_GEOJSON_FEATURES)


@pytest.mark.parametrize("channel", get_test_channels())
def test_get_users(client: TestClient, channel: str):
    response = client.get(f"/channel/{channel}/users")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("channel", get_test_channels())
def test_put_message(client: TestClient, channel: str):
    response = client.put(
        f"/channel/{channel}/text",
        json={
            "type": QChatMessageTypeEnum.TEXT.value,
            "author": f"ws-tester-{channel}",
            "avatar": "postgis",
            "text": "fromage",
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "fromage"
    assert response.json()["author"] == f"ws-tester-{channel}"
    assert response.json()["avatar"] == "postgis"


def test_put_message_wrong_channel(client: TestClient):
    assert (
        client.put(
            "/channel/fromage/text",
            json={
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": "ws-tester",
                "text": "fromage",
            },
        ).status_code
        == 404
    )

    assert (
        client.put(
            "/channel/void/text",
            json={
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": "ws-tester",
                "text": "fromage",
            },
        ).status_code
        == 404
    )


@pytest.mark.parametrize("channel", get_test_channels())
def test_put_message_author_not_alphanum(client: TestClient, channel: str):
    response = client.put(
        f"/channel/{channel}/text",
        json={
            "type": QChatMessageTypeEnum.TEXT.value,
            "author": "<darth_chri$tian>",
            "text": "fromage",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("channel", get_test_channels())
def test_put_message_author_too_short(client: TestClient, channel: str):
    response = client.put(
        f"/channel/{channel}/text",
        json={
            "type": QChatMessageTypeEnum.TEXT.value,
            "author": "ch",
            "avatar": "postgis",
            "text": "fromage",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("channel", get_test_channels())
def test_put_message_author_too_long(client: TestClient, channel: str):
    author = "".join(["a" for _ in range(int(MAX_AUTHOR_LENGTH) + 1)])
    response = client.put(
        f"/channel/{channel}/text",
        json={
            "type": QChatMessageTypeEnum.TEXT.value,
            "author": author,
            "text": "fromage",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("channel", get_test_channels())
def test_put_message_too_long(client: TestClient, channel: str):
    text = "".join(["a" for _ in range(int(MAX_MESSAGE_LENGTH) + 1)])
    response = client.put(
        f"/channel/{channel}/text",
        json={
            "type": QChatMessageTypeEnum.TEXT.value,
            "author": "stephanie",
            "text": text,
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("channel", get_test_channels())
def test_stored_message(client: TestClient, channel: str):
    response = client.get(f"/channel/{channel}/last")

    assert response.status_code == 200
    assert response.json() == []

    client.put(
        f"/channel/{channel}/text",
        json={
            "type": QChatMessageTypeEnum.TEXT.value,
            "author": f"ws-tester-{channel}",
            "avatar": "raster",
            "text": "fromage",
        },
    )
    response = client.get(f"/channel/{channel}/last")

    assert response.status_code == 200
    assert is_subdict(
        {
            "type": QChatMessageTypeEnum.TEXT.value,
            "author": f"ws-tester-{channel}",
            "avatar": "raster",
            "text": "fromage",
        },
        response.json()[0],
    )


@pytest.mark.parametrize("channel", get_test_channels())
def test_stored_multiple(client: TestClient, channel: str):
    for i in range(int(MAX_STORED_MESSAGES) * 2):
        response = client.put(
            f"/channel/{channel}/text",
            json={
                "type": QChatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{channel}",
                "avatar": "raster",
                "text": f"message {i}",
            },
        )
        assert response.status_code == 200

    response = client.get(f"/channel/{channel}/last")

    assert response.status_code == 200
    assert len(response.json()) == int(MAX_STORED_MESSAGES)
