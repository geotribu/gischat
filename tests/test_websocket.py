import pytest
from fastapi.testclient import TestClient

from tests.conftest import test_rooms

TEST_MESSAGE = "Is this websocket working ?"


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_put_message(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        client.put(
            f"/room/{room}/message",
            json={"message": TEST_MESSAGE, "author": f"ws-tester-{room}"},
        )
        data = websocket.receive_json()
        assert data == {"message": TEST_MESSAGE, "author": f"ws-tester-{room}"}


@pytest.mark.parametrize("room", test_rooms())
def test_websocket_send_message(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        websocket.send_json({"message": TEST_MESSAGE, "author": f"ws-tester-{room}"})
        data = websocket.receive_json()
        assert data == {"message": TEST_MESSAGE, "author": f"ws-tester-{room}"}
