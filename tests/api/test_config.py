def test_get_config_404_when_none_set(client, tenant_id):
    response = client.get(f"/v1/tenants/{tenant_id}/config")
    assert response.status_code == 404


def test_put_then_get_config_roundtrips(client, tenant_id):
    payload = {
        "weights": {
            "price": 2.0,
            "shipping_speed": 1.0,
            "seller_rating": 1.0,
            "dispatch_time": 1.0,
            "return_rate": 1.0,
        },
        "min_seller_rating": 3.5,
        "min_stock_qty": 2,
        "max_price_tolerance_pct": 15.0,
    }
    put_response = client.put(f"/v1/tenants/{tenant_id}/config", json=payload)
    assert put_response.status_code == 200
    assert put_response.json()["version"] == 1

    get_response = client.get(f"/v1/tenants/{tenant_id}/config")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["version"] == 1
    assert body["weights"]["price"] == 2.0
    assert body["min_seller_rating"] == 3.5


def test_put_config_twice_increments_version(client, tenant_id):
    payload = {
        "weights": {},
        "min_seller_rating": 0,
        "min_stock_qty": 1,
        "max_price_tolerance_pct": 100,
    }
    client.put(f"/v1/tenants/{tenant_id}/config", json=payload)
    second = client.put(f"/v1/tenants/{tenant_id}/config", json=payload)

    assert second.json()["version"] == 2


def test_put_config_for_unknown_tenant_fails_auth_before_reaching_tenant_check(client):
    # The fake API-key store only issues a key for the test tenant, so an unrecognized
    # tenant_id fails auth (401) before the route ever checks whether the tenant exists.
    # This is intentional: auth should fail closed without leaking tenant existence.
    payload = {
        "weights": {},
        "min_seller_rating": 0,
        "min_stock_qty": 1,
        "max_price_tolerance_pct": 100,
    }
    response = client.put("/v1/tenants/does-not-exist/config", json=payload)
    assert response.status_code == 401


def test_put_config_for_unknown_tenant_404s_when_authenticated(client, monkeypatch):
    from buybox.api.auth import ApiKeyStore, set_api_key_store

    class AllowAnyTenantStore(ApiKeyStore):
        def get_key_for_tenant(self, tenant_id: str) -> str | None:
            return "test-api-key"

    set_api_key_store(AllowAnyTenantStore())
    payload = {
        "weights": {},
        "min_seller_rating": 0,
        "min_stock_qty": 1,
        "max_price_tolerance_pct": 100,
    }
    response = client.put("/v1/tenants/does-not-exist/config", json=payload)
    assert response.status_code == 404


def test_config_endpoints_require_api_key(client, tenant_id):
    client.headers.pop("X-API-Key")
    response = client.get(f"/v1/tenants/{tenant_id}/config")
    assert response.status_code in (401, 422)
