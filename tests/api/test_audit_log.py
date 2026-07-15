from buybox.domain.models import TenantRuleConfig
from buybox.persistence.repositories import TenantConfigRepository
from tests.api.test_rank import _rank_payload


def test_audit_log_records_ranking_calls(client, db_session, tenant_id):
    TenantConfigRepository().add_version(
        db_session, TenantRuleConfig(tenant_id=tenant_id, version=1)
    )
    client.post(f"/v1/tenants/{tenant_id}/rank", json=_rank_payload())

    response = client.get(f"/v1/tenants/{tenant_id}/audit-log", params={"listing_id": "listing-1"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["winner_seller_id"] == "seller-a"


def test_audit_log_empty_when_no_ranking_calls(client, tenant_id):
    response = client.get(f"/v1/tenants/{tenant_id}/audit-log", params={"listing_id": "listing-1"})

    assert response.status_code == 200
    assert response.json()["entries"] == []
