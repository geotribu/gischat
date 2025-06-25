import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from gischat.app import WebsocketNotifier
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


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    os.environ["ROOMS"] = ",".join(TEST_ROOMS)
    os.environ["RULES"] = TEST_RULES
    os.environ["MIN_AUTHOR_LENGTH"] = MIN_AUTHOR_LENGTH
    os.environ["MAX_MESSAGE_LENGTH"] = MAX_MESSAGE_LENGTH
    os.environ["MAX_IMAGE_SIZE"] = MAX_IMAGE_SIZE
    os.environ["MAX_GEOJSON_FEATURES"] = MAX_GEOJSON_FEATURES
    os.environ["REDIS_PORT"] = "16379"
    from gischat.app import app

    yield TestClient(app)


@pytest.fixture(autouse=True)
def run_around_tests() -> Generator:
    """
    Runs around each test
    """
    notifier = WebsocketNotifier.instance()
    notifier.clear_stored_messages()
    yield
