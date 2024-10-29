import pytest
from fastapi.testclient import TestClient

from gischat.models import GischatMessageTypeEnum
from gischat.utils import get_poetry_version
from tests import (
    MAX_AUTHOR_LENGTH,
    MAX_GEOJSON_FEATURES,
    MAX_IMAGE_SIZE,
    MAX_MESSAGE_LENGTH,
    MAX_STORED_MESSAGES,
    MIN_AUTHOR_LENGTH,
    TEST_RULES,
)
from tests.conftest import get_test_rooms


def test_get_version(client: TestClient):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["version"] == get_poetry_version()


@pytest.mark.parametrize("room", get_test_rooms())
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


@pytest.mark.parametrize("room", get_test_rooms())
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
    assert response.json()["max_image_size"] == int(MAX_IMAGE_SIZE)
    assert response.json()["max_geojson_features"] == int(MAX_GEOJSON_FEATURES)


@pytest.mark.parametrize("room", get_test_rooms())
def test_get_users(client: TestClient, room: str):
    response = client.get(f"/room/{room}/users")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("room", get_test_rooms())
def test_put_message(client: TestClient, room: str):
    response = client.put(
        f"/room/{room}/text",
        json={
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": f"ws-tester-{room}",
            "avatar": "postgis",
            "text": "fromage",
        },
    )
    assert response.status_code == 200
    assert response.json()["text"] == "fromage"
    assert response.json()["author"] == f"ws-tester-{room}"
    assert response.json()["avatar"] == "postgis"


def test_put_message_wrong_room(client: TestClient):
    assert (
        client.put(
            "/room/fromage/text",
            json={
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": "ws-tester",
                "text": "fromage",
            },
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/room/void/text",
            json={
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": "ws-tester",
                "text": "fromage",
            },
        ).status_code
        == 404
    )


@pytest.mark.parametrize("room", get_test_rooms())
def test_put_message_author_not_alphanum(client: TestClient, room: str):
    response = client.put(
        f"/room/{room}/text",
        json={
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": "<darth_chri$tian>",
            "text": "fromage",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("room", get_test_rooms())
def test_put_message_author_too_short(client: TestClient, room: str):
    response = client.put(
        f"/room/{room}/text",
        json={
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": "ch",
            "avatar": "postgis",
            "text": "fromage",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("room", get_test_rooms())
def test_put_message_author_too_long(client: TestClient, room: str):
    author = "".join(["a" for _ in range(int(MAX_AUTHOR_LENGTH) + 1)])
    response = client.put(
        f"/room/{room}/text",
        json={
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": author,
            "text": "fromage",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("room", get_test_rooms())
def test_put_message_too_long(client: TestClient, room: str):
    text = "".join(["a" for _ in range(int(MAX_MESSAGE_LENGTH) + 1)])
    response = client.put(
        f"/room/{room}/text",
        json={
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": "stephanie",
            "text": text,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("room", get_test_rooms())
def test_stored_message(client: TestClient, room: str):
    response = client.get(f"/room/{room}/last")
    assert response.status_code == 200
    assert response.json() == []
    client.put(
        f"/room/{room}/text",
        json={
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": f"ws-tester-{room}",
            "avatar": "raster",
            "text": "fromage",
        },
    )
    response = client.get(f"/room/{room}/last")
    assert response.status_code == 200
    assert response.json() == [
        {
            "type": GischatMessageTypeEnum.TEXT.value,
            "author": f"ws-tester-{room}",
            "avatar": "raster",
            "text": "fromage",
        }
    ]


@pytest.mark.parametrize("room", get_test_rooms())
def test_stored_multiple(client: TestClient, room: str):
    for i in range(int(MAX_STORED_MESSAGES) * 2):
        response = client.put(
            f"/room/{room}/text",
            json={
                "type": GischatMessageTypeEnum.TEXT.value,
                "author": f"ws-tester-{room}",
                "avatar": "raster",
                "text": f"message {i}",
            },
        )
        assert response.status_code == 200
    response = client.get(f"/room/{room}/last")
    assert response.status_code == 200
    assert len(response.json()) == int(MAX_STORED_MESSAGES)
