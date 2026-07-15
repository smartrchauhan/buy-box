from buybox.domain.models import TenantRuleConfig
from buybox.persistence.repositories import TenantConfigRepository


def _rank_payload() -> dict:
    return {
        "listing_id": "listing-1",
        "offers": [
            {
                "seller_id": "seller-a",
                "price": "90.00",
                "shipping_cost": "0.00",
                "shipping_speed_days": 2,
                "stock_qty": 10,
                "fulfillment_type": "seller_fulfilled",
                "seller_rating": 4.5,
                "dispatch_time_hours": 24,
                "return_rate": 0.02,
            },
            {
                "seller_id": "seller-b",
                "price": "100.00",
                "shipping_cost": "0.00",
                "shipping_speed_days": 2,
                "stock_qty": 10,
                "fulfillment_type": "seller_fulfilled",
                "seller_rating": 4.5,
                "dispatch_time_hours": 24,
                "return_rate": 0.02,
            },
        ],
    }


def test_rank_without_config_returns_404(client, tenant_id):
    response = client.post(f"/v1/tenants/{tenant_id}/rank", json=_rank_payload())
    assert response.status_code == 404


def test_rank_with_config_returns_winner(client, db_session, tenant_id):
    TenantConfigRepository().add_version(
        db_session, TenantRuleConfig(tenant_id=tenant_id, version=1)
    )

    response = client.post(f"/v1/tenants/{tenant_id}/rank", json=_rank_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["winner"]["seller_id"] == "seller-a"
    assert len(body["scores"]) == 2


def test_rank_requires_api_key(client, db_session, tenant_id):
    TenantConfigRepository().add_version(
        db_session, TenantRuleConfig(tenant_id=tenant_id, version=1)
    )
    client.headers.pop("X-API-Key")

    response = client.post(f"/v1/tenants/{tenant_id}/rank", json=_rank_payload())

    assert response.status_code in (401, 422)
