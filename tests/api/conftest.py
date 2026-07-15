import pytest
from fastapi.testclient import TestClient

from buybox.api.app import create_app
from buybox.api.auth import ApiKeyStore, set_api_key_store
from buybox.api.deps import get_db

TEST_TENANT_ID = "tenant-test"
TEST_API_KEY = "test-api-key"


class FakeApiKeyStore(ApiKeyStore):
    def get_key_for_tenant(self, tenant_id: str) -> str | None:
        return TEST_API_KEY if tenant_id == TEST_TENANT_ID else None


@pytest.fixture
def client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    set_api_key_store(FakeApiKeyStore())

    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": TEST_API_KEY})
        yield test_client

    app.dependency_overrides.clear()
