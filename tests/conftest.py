import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from tests import MAX_MESSAGE_LENGTH, MIN_AUTHOR_LENGTH, TEST_ROOMS, TEST_RULES


def get_test_rooms() -> list[str]:
    return TEST_ROOMS


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    os.environ["ROOMS"] = ",".join(TEST_ROOMS)
    os.environ["RULES"] = TEST_RULES
    os.environ["MIN_AUTHOR_LENGTH"] = MIN_AUTHOR_LENGTH
    os.environ["MAX_MESSAGE_LENGTH"] = MAX_MESSAGE_LENGTH
    from gischat.app import app

    yield TestClient(app)
