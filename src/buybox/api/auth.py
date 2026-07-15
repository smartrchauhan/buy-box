"""Per-tenant API-key authentication.

Kept behind an abstract `ApiKeyStore` so route code never changes when Phase 4 swaps the
local env-var-backed store for a real AWS Secrets Manager-backed one.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod

from fastapi import Header, HTTPException, status


class ApiKeyStore(ABC):
    @abstractmethod
    def get_key_for_tenant(self, tenant_id: str) -> str | None: ...


class EnvApiKeyStore(ApiKeyStore):
    """Local/dev implementation: reads a JSON object of {tenant_id: api_key} from an env var.

    Not for QA/PROD use — Phase 4 replaces this with a Secrets-Manager-backed store.
    """

    def __init__(self, env_var: str = "TENANT_API_KEYS") -> None:
        self._env_var = env_var

    def get_key_for_tenant(self, tenant_id: str) -> str | None:
        raw = os.environ.get(self._env_var, "{}")
        keys: dict[str, str] = json.loads(raw)
        return keys.get(tenant_id)


_store: ApiKeyStore = EnvApiKeyStore()


def get_api_key_store() -> ApiKeyStore:
    return _store


def set_api_key_store(store: ApiKeyStore) -> None:
    """Test/deployment hook to swap the store implementation (e.g. in Phase 4's Lambda init)."""
    global _store
    _store = store


def require_tenant_api_key(tenant_id: str, x_api_key: str = Header(...)) -> None:
    store = get_api_key_store()
    expected = store.get_key_for_tenant(tenant_id)
    if expected is None or x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
