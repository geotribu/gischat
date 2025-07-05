import os
from collections.abc import Generator

import pytest_asyncio
from fastapi import FastAPI
from redis import Redis as RedisObject
from starlette.testclient import TestClient

from gischat.app import app
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

redis_connection = RedisObject(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
)


def get_test_rooms() -> list[str]:
    return TEST_ROOMS


@pytest_asyncio.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
def fastapi_app() -> FastAPI:
    os.environ["ROOMS"] = ",".join(TEST_ROOMS)
    os.environ["RULES"] = TEST_RULES
    os.environ["MIN_AUTHOR_LENGTH"] = MIN_AUTHOR_LENGTH
    os.environ["MAX_MESSAGE_LENGTH"] = MAX_MESSAGE_LENGTH
    os.environ["MAX_IMAGE_SIZE"] = MAX_IMAGE_SIZE
    os.environ["MAX_GEOJSON_FEATURES"] = MAX_GEOJSON_FEATURES
    os.environ["INSTANCE_ID"] = "abcdefg"

    dispatcher = RedisWebsocketDispatcher.instance()

    dispatcher.init_redis(
        pub=redis_connection,
        sub=redis_connection,
        connection=redis_connection,
    )

    return app


@pytest_asyncio.fixture(scope="session")
def client(fastapi_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app=fastapi_app, base_url="http://testserver") as test_client:
        yield test_client


@pytest_asyncio.fixture(scope="function", autouse=True)
def run_around_tests() -> Generator:
    redis_connection.flushdb()
    yield
