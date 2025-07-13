from time import sleep

import pytest
from starlette.testclient import TestClient

from gischat.models import GischatMessageTypeEnum
from tests.conftest import get_test_rooms
from tests.test_utils import is_subdict


@pytest.mark.parametrize("room", get_test_rooms())
def test_websocket_like_message(client: TestClient, room: str):
    # register client 1 (Isidore)
    with client.websocket_connect(f"/room/{room}/ws") as websocket1:

        assert is_subdict(
            {
                "type": GischatMessageTypeEnum.NB_USERS.value,
                "nb_users": 1,
            },
            websocket1.receive_json(),
        )

        websocket1.send_json(
            {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "Isidore"}
        )

        assert is_subdict(
            {
                "type": GischatMessageTypeEnum.NEWCOMER.value,
                "newcomer": "Isidore",
            },
            websocket1.receive_json(),
        )

        # register client 2 (Barnabe)
        with client.websocket_connect(f"/room/{room}/ws") as websocket2:

            assert is_subdict(
                {
                    "type": GischatMessageTypeEnum.NB_USERS.value,
                    "nb_users": 2,
                },
                websocket1.receive_json(),
            )
            assert is_subdict(
                {
                    "type": GischatMessageTypeEnum.NB_USERS.value,
                    "nb_users": 2,
                },
                websocket2.receive_json(),
            )

            websocket2.send_json(
                {"type": GischatMessageTypeEnum.NEWCOMER.value, "newcomer": "Barnabe"}
            )

            assert is_subdict(
                {
                    "type": GischatMessageTypeEnum.NEWCOMER.value,
                    "newcomer": "Barnabe",
                },
                websocket2.receive_json(),
            )
            assert is_subdict(
                {
                    "type": GischatMessageTypeEnum.NEWCOMER.value,
                    "newcomer": "Barnabe",
                },
                websocket1.receive_json(),
            )

            # client 1 sends a message
            websocket1.send_json(
                {
                    "type": GischatMessageTypeEnum.TEXT.value,
                    "author": "Isidore",
                    "avatar": "postgis",
                    "text": "hi",
                }
            )

            assert is_subdict(
                {
                    "type": GischatMessageTypeEnum.TEXT.value,
                    "author": "Isidore",
                    "avatar": "postgis",
                    "text": "hi",
                },
                websocket1.receive_json(),
            )
            assert is_subdict(
                {
                    "type": GischatMessageTypeEnum.TEXT.value,
                    "author": "Isidore",
                    "avatar": "postgis",
                    "text": "hi",
                },
                websocket2.receive_json(),
            )

            # client 2 likes client 1's message
            websocket2.send_json(
                {
                    "type": GischatMessageTypeEnum.LIKE.value,
                    "liker_author": "Barnabe",
                    "liked_author": "Isidore",
                    "message": "hi",
                }
            )
            sleep(1)

            assert is_subdict(
                {
                    "type": GischatMessageTypeEnum.LIKE.value,
                    "liker_author": "Barnabe",
                    "liked_author": "Isidore",
                    "message": "hi",
                },
                websocket1.receive_json(),
            )
