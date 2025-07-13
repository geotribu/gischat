import pytest
from starlette.testclient import TestClient

from gischat.models import GischatMessageTypeEnum
from tests import WGS84_AUTHID, WGS84_WKT
from tests.conftest import get_test_rooms
from tests.test_utils import is_subdict


@pytest.mark.parametrize("room", get_test_rooms())
def test_send_and_receive_geojson(client: TestClient, room: str):
    with client.websocket_connect(f"/room/{room}/ws") as websocket:

        assert is_subdict(
            {
                "type": GischatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket.receive_json(),
        )

        websocket.send_json(
            {
                "type": GischatMessageTypeEnum.BBOX.value,
                "author": f"ws-tester-{room}",
                "avatar": "cat",
                "crs_wkt": WGS84_WKT,
                "crs_authid": WGS84_AUTHID,
                "xmin": -1.1,
                "xmax": 1.1,
                "ymin": -1.1,
                "ymax": 1.1,
            }
        )
        data = websocket.receive_json()

        assert is_subdict(
            {
                "type": GischatMessageTypeEnum.BBOX.value,
                "author": f"ws-tester-{room}",
                "avatar": "cat",
                "crs_wkt": WGS84_WKT,
                "crs_authid": WGS84_AUTHID,
                "xmin": -1.1,
                "xmax": 1.1,
                "ymin": -1.1,
                "ymax": 1.1,
            },
            data,
        )

    response = client.get(f"/room/{room}/last")

    assert response.status_code == 200
    assert is_subdict(
        {
            "type": GischatMessageTypeEnum.BBOX.value,
            "author": f"ws-tester-{room}",
            "avatar": "cat",
            "crs_wkt": WGS84_WKT,
            "crs_authid": WGS84_AUTHID,
            "xmin": -1.1,
            "xmax": 1.1,
            "ymin": -1.1,
            "ymax": 1.1,
        },
        response.json()[0],
    )
