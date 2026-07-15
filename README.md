# Buy Box Engine

Multi-tenant buy-box (offer-ranking) engine, built as a sellable B2B product for marketplace
operators. See [`architecture.md`](./architecture.md) for the full phased design — this
README only covers day-to-day local development.

## Prerequisites

- Python 3.13
- [Poetry](https://python-poetry.org/)
- Docker + Docker Compose

## Local development

```bash
cp .env.local.example .env.local   # adjust if needed; this file is gitignored
poetry install
make up          # starts Postgres + LocalStack (SQS, Secrets Manager) in Docker
make test-local  # runs the full local test suite (pytest)
make down         # stops the local stack
```

Other useful targets:

```bash
make lint        # ruff check
make fmt         # ruff format
make typecheck   # mypy on src/
```

## Environments

| Env    | Where it runs                         | Cost         |
|--------|----------------------------------------|--------------|
| local  | Docker Compose (Postgres + LocalStack) | $0           |
| qa     | AWS (single-AZ RDS, Lambda)            | ≈ $15–25/mo  |
| prod   | AWS (Multi-AZ RDS, Lambda, WAF)        | ≈ $50–80/mo  |

Real QA/PROD credentials and API keys live only in AWS Secrets Manager — never in a
committed file. `.env.qa.example` / `.env.prod.example` document the non-secret config keys
only.

## Project layout

- `src/buybox/` — application code (domain logic, persistence, API)
- `tests/` — mirrors `src/`, plus `tests/smoke/` for post-deploy checks (added in later phases)
- `infra/` — AWS CDK (Python) infrastructure-as-code (added in Phase 4)
- `docs/` — runbooks and supporting docs
