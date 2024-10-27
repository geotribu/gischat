import json

import pytest
from starlette.testclient import TestClient

from gischat.models import GischatMessageTypeEnum
from tests import MAX_GEOJSON_FEATURES, WGS84_AUTHID, WGS84_WKT
from tests.conftest import get_test_rooms

GEOJSON_PATH_OK = "tests/data/tissot.geojson"
GEOJSON_PATH_NOK = "tests/data/points.geojson"


@pytest.mark.parametrize("room", get_test_rooms())
def test_send_and_receive_geojson(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        with open(GEOJSON_PATH_OK) as file:
            websocket.send_json(
                {
                    "type": GischatMessageTypeEnum.GEOJSON.value,
                    "author": f"ws-tester-{room}",
                    "avatar": "cat",
                    "layer_name": "tissot",
                    "crs_wkt": WGS84_WKT,
                    "crs_authid": WGS84_AUTHID,
                    "geojson": json.load(file),
                }
            )
        data = websocket.receive_json()
        assert data["type"] == GischatMessageTypeEnum.GEOJSON.value
        assert data["author"] == f"ws-tester-{room}"
        assert data["avatar"] == "cat"
        assert data["layer_name"] == "tissot"
        assert data["crs_wkt"] == WGS84_WKT
        assert data["crs_authid"] == WGS84_AUTHID
        assert data["geojson"]["type"] == "FeatureCollection"
        assert len(data["geojson"]["features"]) == 60


@pytest.mark.parametrize("room", get_test_rooms())
def test_send_wrong_geojson(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.NB_USERS.value,
            "nb_users": 1,
        }
        with open(GEOJSON_PATH_NOK) as file:
            websocket.send_json(
                {
                    "type": GischatMessageTypeEnum.GEOJSON.value,
                    "author": f"ws-tester-{room}",
                    "avatar": "cat",
                    "layer_name": "points",
                    "crs_wkt": WGS84_WKT,
                    "crs_authid": WGS84_AUTHID,
                    "geojson": json.load(file),
                }
            )
        assert websocket.receive_json() == {
            "type": GischatMessageTypeEnum.UNCOMPLIANT.value,
            "reason": f"Too many geojson features : 501 vs max {int(MAX_GEOJSON_FEATURES)} allowed",
        }
