"""Phase 0 sanity checks: confirm the local dev loop (pytest, Postgres, LocalStack) works."""

import os

import psycopg2
import pytest


def test_pytest_runs() -> None:
    assert 1 + 1 == 2


@pytest.mark.skipif(
    os.environ.get("BUYBOX_SKIP_DOCKER_TESTS") == "1",
    reason="Docker services not running",
)
def test_postgres_reachable() -> None:
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://buybox:buybox_local_only@localhost:5432/buybox"
    )
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            assert cur.fetchone() == (1,)
    finally:
        conn.close()


@pytest.mark.skipif(
    os.environ.get("BUYBOX_SKIP_DOCKER_TESTS") == "1",
    reason="Docker services not running",
)
def test_localstack_sqs_reachable() -> None:
    import boto3

    sqs = boto3.client(
        "sqs",
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    response = sqs.list_queues()
    assert "ResponseMetadata" in response
