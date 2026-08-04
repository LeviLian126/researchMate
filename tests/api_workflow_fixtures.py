"""Provide isolated local-store and HTTP-client fixtures for API workflow tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from researchmate_api.config import Settings
from researchmate_api.main import create_app
from researchmate_api.services.store import store


@pytest.fixture(autouse=True)
def reset_local_store() -> Generator[None]:
    """Reset shared local persistence before and after each workflow test."""
    store.reset()
    yield
    store.reset()


@pytest.fixture()
def client() -> TestClient:
    """Build the fake-provider application used by HTTP workflow tests."""
    return TestClient(create_app(settings=Settings(app_env="test", llm_provider="fake")))
