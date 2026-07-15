from buybox.persistence.repositories import TenantRepository


def test_create_and_get_tenant(db_session):
    repo = TenantRepository()
    repo.create(db_session, tenant_id="acme", name="Acme Marketplace")

    fetched = repo.get(db_session, "acme")

    assert fetched is not None
    assert fetched.tenant_id == "acme"
    assert fetched.name == "Acme Marketplace"


def test_get_missing_tenant_returns_none(db_session):
    repo = TenantRepository()

    assert repo.get(db_session, "does-not-exist") is None
