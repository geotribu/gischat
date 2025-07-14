import base64
from io import BytesIO

import pytest
from PIL import Image
from starlette.testclient import TestClient

from gischat.models import QChatMessageTypeEnum
from tests import MAX_IMAGE_SIZE
from tests.conftest import get_test_channels
from tests.test_utils import is_subdict

CAT_IMAGE_PATH = "tests/img/cat.jpg"


@pytest.mark.parametrize("channel", get_test_channels())
def test_send_image_resized(client: TestClient, channel: str):
    original_image = Image.open(CAT_IMAGE_PATH)
    ow, oh = original_image.size

    assert ow == 1200
    assert oh == 800

    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket.receive_json(),
        )

        with open(CAT_IMAGE_PATH, "rb") as file:
            image_data = file.read()
            websocket.send_json(
                {
                    "type": QChatMessageTypeEnum.IMAGE.value,
                    "author": f"ws-tester-{channel}",
                    "avatar": "cat",
                    "image_data": base64.b64encode(image_data).decode("utf-8"),
                }
            )
            data = websocket.receive_json()

            assert data["type"] == QChatMessageTypeEnum.IMAGE.value
            assert data["author"] == f"ws-tester-{channel}"
            assert data["avatar"] == "cat"
            assert "image_data" in data
            assert data["image_data"]

            image = Image.open(BytesIO(base64.b64decode(data["image_data"])))
            w, h = image.size

            assert max(w, h) == int(MAX_IMAGE_SIZE)
