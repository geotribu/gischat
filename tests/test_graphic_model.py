import pytest
from starlette.testclient import TestClient

from gischat.models import GischatMessageTypeEnum
from tests.conftest import get_test_rooms


@pytest.mark.parametrize("room", get_test_rooms())
def test_send_and_receive_geojson(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:

        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }

        websocket.send_json(
            {
                "type": GischatMessageTypeEnum.MODEL.value,
                "author": f"ws-tester-{room}",
                "avatar": "cat",
                "model_name": "La PR, la PR, mais qu'est-ce qu'elle a fait de moi la PR ? La PR, la PR, c'est comme si c'était mon frère.",
                "model_group": "Les Barçons Gouchers",
                "raw_xml": "<xml>Some graphic model XML</xml>",
            }
        )
        data = websocket.receive_json()

        assert data["type"] == GischatMessageTypeEnum.MODEL.value
        assert data["author"] == f"ws-tester-{room}"
        assert data["avatar"] == "cat"
        assert (
            data["model_name"]
            == "La PR, la PR, mais qu'est-ce qu'elle a fait de moi la PR ? La PR, la PR, c'est comme si c'était mon frère."
        )
        assert data["model_group"] == "Les Barçons Gouchers"
        assert data["raw_xml"] == "<xml>Some graphic model XML</xml>"
