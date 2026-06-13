import pytest
from starlette.testclient import TestClient

from gischat.models import QChatMessageTypeEnum
from tests.conftest import get_test_channels
from tests.test_utils import is_subdict


@pytest.mark.parametrize("channel", get_test_channels())
def test_send_and_receive_script(client: TestClient, channel: str):
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
                "type": QChatMessageTypeEnum.SCRIPT.value,
                "author": f"ws-tester-{channel}",
                "avatar": "cat",
                "name": "Pyscript test script",
                "raw_pycode": "from qgis.core import QgsProject",
            }
        )
        data = websocket.receive_json()

        assert data["type"] == QChatMessageTypeEnum.SCRIPT.value
        assert data["author"] == f"ws-tester-{channel}"
        assert data["avatar"] == "cat"
        assert data["name"] == "Pyscript test script"
        assert data["raw_pycode"] == "from qgis.core import QgsProject"
