import pytest
from starlette.testclient import TestClient

from gischat.models import QChatMessageTypeEnum
from tests.conftest import get_test_channels
from tests.test_utils import is_subdict


@pytest.mark.parametrize("channel", get_test_channels())
def test_send_and_receive_geojson(client: TestClient, channel: str):
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
                "type": QChatMessageTypeEnum.MODEL.value,
                "author": f"ws-tester-{channel}",
                "avatar": "cat",
                "model_name": "La PR, la PR, mais qu'est-ce qu'elle a fait de moi la PR ? La PR, la PR, c'est comme si c'était mon frère.",
                "model_group": "Les Barçons Gouchers",
                "raw_xml": "<xml>Some graphic model XML</xml>",
            }
        )
        data = websocket.receive_json()

        assert data["type"] == QChatMessageTypeEnum.MODEL.value
        assert data["author"] == f"ws-tester-{channel}"
        assert data["avatar"] == "cat"
        assert (
            data["model_name"]
            == "La PR, la PR, mais qu'est-ce qu'elle a fait de moi la PR ? La PR, la PR, c'est comme si c'était mon frère."
        )
        assert data["model_group"] == "Les Barçons Gouchers"
        assert data["raw_xml"] == "<xml>Some graphic model XML</xml>"
