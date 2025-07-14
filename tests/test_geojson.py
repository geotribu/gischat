import json

import pytest
from starlette.testclient import TestClient

from gischat.models import QChatMessageTypeEnum
from tests import MAX_GEOJSON_FEATURES, WGS84_AUTHID, WGS84_WKT
from tests.conftest import get_test_channels
from tests.test_utils import is_subdict

GEOJSON_PATH_OK = "tests/data/tissot.geojson"
GEOJSON_PATH_NOK = "tests/data/points.geojson"


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

        with open(GEOJSON_PATH_OK) as file:
            websocket.send_json(
                {
                    "type": QChatMessageTypeEnum.GEOJSON.value,
                    "author": f"ws-tester-{channel}",
                    "avatar": "cat",
                    "layer_name": "tissot",
                    "crs_wkt": WGS84_WKT,
                    "crs_authid": WGS84_AUTHID,
                    "geojson": json.load(file),
                    "style": "<xml>Some QML style</xml>",
                }
            )
        data = websocket.receive_json()

        assert data["type"] == QChatMessageTypeEnum.GEOJSON.value
        assert data["author"] == f"ws-tester-{channel}"
        assert data["avatar"] == "cat"
        assert data["layer_name"] == "tissot"
        assert data["crs_wkt"] == WGS84_WKT
        assert data["crs_authid"] == WGS84_AUTHID
        assert data["geojson"]["type"] == "FeatureCollection"
        assert data["style"] == "<xml>Some QML style</xml>"
        assert len(data["geojson"]["features"]) == 60


@pytest.mark.parametrize("channel", get_test_channels())
def test_send_wrong_geojson(client: TestClient, channel: str):
    with client.websocket_connect(f"/channel/{channel}/ws") as websocket:

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket.receive_json(),
        )

        with open(GEOJSON_PATH_NOK) as file:
            websocket.send_json(
                {
                    "type": QChatMessageTypeEnum.GEOJSON.value,
                    "author": f"ws-tester-{channel}",
                    "avatar": "cat",
                    "layer_name": "points",
                    "crs_wkt": WGS84_WKT,
                    "crs_authid": WGS84_AUTHID,
                    "geojson": json.load(file),
                }
            )

        assert is_subdict(
            {
                "type": QChatMessageTypeEnum.UNCOMPLIANT.value,
                "reason": f"Too many geojson features : 501 vs max {int(MAX_GEOJSON_FEATURES)} allowed",
            },
            websocket.receive_json(),
        )
