from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from tests.fakes import FakeHorizonsClient


@pytest.fixture
def fake_horizons() -> FakeHorizonsClient:
    return FakeHorizonsClient()


@pytest.fixture
def client(fake_horizons: FakeHorizonsClient):
    app.dependency_overrides[deps.get_horizons_client] = lambda: fake_horizons
    deps.get_analysis_store().clear()
    deps.get_ephemeris_cache().clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
