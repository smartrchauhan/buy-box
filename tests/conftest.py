import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from buybox.persistence.models import Base
from buybox.persistence.repositories import TenantRepository


@pytest.fixture(scope="session")
def engine():
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://buybox:buybox_local_only@localhost:5432/buybox"
    )
    eng = create_engine(database_url)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def tenant_id(db_session) -> str:
    TenantRepository().create(db_session, tenant_id="tenant-test", name="Test Tenant")
    return "tenant-test"
