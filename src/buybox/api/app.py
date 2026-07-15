from __future__ import annotations

from fastapi import FastAPI

from buybox.api.routes import audit_log, config, rank


def create_app() -> FastAPI:
    app = FastAPI(title="Buy Box Engine API", version="0.1.0")
    app.include_router(rank.router)
    app.include_router(config.router)
    app.include_router(audit_log.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
