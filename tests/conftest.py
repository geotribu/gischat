import os
from collections.abc import Generator

import pytest
from redis import Redis as RedisObject
from starlette.testclient import TestClient

from gischat.dispatchers import RedisWebsocketDispatcher
from gischat.env import REDIS_HOST, REDIS_PORT
from tests import (
    MAX_GEOJSON_FEATURES,
    MAX_IMAGE_SIZE,
    MAX_MESSAGE_LENGTH,
    MIN_AUTHOR_LENGTH,
    TEST_ROOMS,
    TEST_RULES,
)


def get_test_rooms() -> list[str]:
    return TEST_ROOMS


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    os.environ["ROOMS"] = ",".join(TEST_ROOMS)
    os.environ["RULES"] = TEST_RULES
    os.environ["MIN_AUTHOR_LENGTH"] = MIN_AUTHOR_LENGTH
    os.environ["MAX_MESSAGE_LENGTH"] = MAX_MESSAGE_LENGTH
    os.environ["MAX_IMAGE_SIZE"] = MAX_IMAGE_SIZE
    os.environ["MAX_GEOJSON_FEATURES"] = MAX_GEOJSON_FEATURES
    from gischat.app import app

    with TestClient(app=app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def run_around_tests() -> Generator:
    """
    Runs around each test
    """
    dispatcher = RedisWebsocketDispatcher.instance()

    redis_connection = RedisObject(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
    )

    dispatcher.init_redis(
        pub=redis_connection,
        sub=redis_connection,
        connection=redis_connection,
    )

    dispatcher.clear_stored_messages()
    yield
