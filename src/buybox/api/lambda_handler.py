"""Lambda entrypoint. Wraps the same FastAPI app used locally via uvicorn — no route code
differs between local and Lambda deployment.
"""

from __future__ import annotations

from typing import Any

from mangum import Mangum

from buybox.api.app import app

handler = Mangum(app)


def lambda_handler(event: dict[str, Any], context: Any) -> Any:
    return handler(event, context)
