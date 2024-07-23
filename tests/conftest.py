import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from tests import TEST_ROOMS, TEST_RULES


def test_rooms() -> list[str]:
    return TEST_ROOMS


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    os.environ["ROOMS"] = ",".join(TEST_ROOMS)
    os.environ["RULES"] = TEST_RULES
    from gischat.app import app

    yield TestClient(app)
