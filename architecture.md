# Buy Box Engine — Architecture & Phased Build Plan

## 0. Overview

**What this is:** A multi-tenant "Buy Box Engine" — given multiple sellers' offers for the
same listing, decide which offer wins the featured slot (like Amazon's Buy Box). Sold as a
B2B SaaS/API product to companies that run their own multi-vendor marketplaces. The author of
this doc is the vendor; marketplace operators are the tenants.

**Starting point:** Greenfield. No marketplace, no code, no infra yet. Paid AWS account
available for deployment.

**Non-negotiable tenets (apply to every phase, restate in every bootstrap prompt):**
- Security: secrets only ever in AWS Secrets Manager, never in git or plain env files that get
  committed. IAM least-privilege per Lambda function. TLS in transit everywhere. Encryption at
  rest for RDS and S3.
- No data loss: automated RDS snapshots + point-in-time recovery, Multi-AZ in PROD, deletion
  protection on PROD RDS, dead-letter queues on all async processing.
- Cost discipline: Local = $0. QA ≈ $15–25/mo. PROD ≈ $50–80/mo at low traffic, scaling with
  usage, never a large fixed cost. Achieved by using Lambda (pay-per-request) over always-on
  containers, and single small RDS instances over Aurora Serverless's always-on minimum ACU.
- Every environment (local/QA/PROD) must be independently testable without touching the others.

**Chosen stack (rationale):**
- **Language**: Python everywhere (app + infra-as-code).
- **API**: FastAPI, wrapped for AWS Lambda via Mangum; runs natively with `uvicorn` locally.
- **Compute**: AWS Lambda + API Gateway (HTTP API) — not ECS/Fargate. Pay-per-request fits
  pre-revenue traffic and "free to cheap" better than an always-on container. Revisit only if
  sustained steady traffic makes Lambda's per-invocation cost exceed a container's baseline.
- **Database**: RDS Postgres, single small instance (`db.t4g.micro` or similar), Multi-AZ only
  in PROD. Chosen over Aurora Serverless v2 because Aurora's always-on minimum ACU costs more
  than a small RDS instance at low, spiky traffic.
- **IaC**: AWS CDK (Python) — one language across app and infra, first-class multi-stage
  support via CDK context.
- **Local dev**: Docker Compose running Postgres + LocalStack (emulates SQS and Secrets
  Manager), so the full stack runs with zero AWS spend and no network dependency.
- **Environments**: `local` (Docker Compose only, no AWS), `qa` (real AWS, single-AZ, small
  instance sizes), `prod` (real AWS, Multi-AZ, deletion protection, WAF). QA and PROD are
  separate CDK stacks; separate AWS accounts (via AWS Organizations) is the long-term target
  for hard isolation, but separate stacks in one account is an acceptable starting point.

**Environment matrix:**

| Aspect            | local                    | qa                          | prod                                |
|-------------------|--------------------------|------------------------------|--------------------------------------|
| Compute            | uvicorn (native process) | Lambda + API Gateway         | Lambda + API Gateway                 |
| DB                 | Dockerized Postgres      | RDS Postgres, single-AZ, small | RDS Postgres, Multi-AZ, deletion protection |
| Queue/Secrets      | LocalStack (SQS, Secrets Manager) | Real SQS + Secrets Manager | Real SQS + Secrets Manager        |
| Cache (Phase 6+)   | none / in-process        | DynamoDB on-demand           | DynamoDB on-demand                   |
| Cost               | $0                       | ≈ $15–25/mo                  | ≈ $50–80/mo at low traffic           |
| Deploy trigger     | manual (`make up`)       | auto on merge to `main`      | manual approval gate after QA smoke tests |

**How to use this doc:** Each phase below is self-contained. To implement a phase in a future
session, copy that phase's entire "Bootstrap prompt" block into Claude — it restates enough
context (repo conventions, prior phases' outputs, this phase's constraints) that no other
history is required.

---

## Phase 0: Repo & local environment scaffolding

**Goal:** Stand up the repo skeleton and a fully working local dev loop with zero AWS
dependency, so every later phase has a consistent place to add code and a fast local
feedback cycle.

**Depends on:** nothing (first phase).

**Deliverables:**
- Python project managed with Poetry (`pyproject.toml`, lockfile).
- Directory layout: `src/buybox/` (application code), `tests/` (mirrors `src/` structure),
  `infra/` (reserved for Phase 4 CDK code), `docs/`.
- Pre-commit hooks: `ruff` (lint + format) and `mypy` (type checking), configured in
  `.pre-commit-config.yaml` and `pyproject.toml`.
- `docker-compose.yml` with two services: `postgres` (official `postgres:16` image) and
  `localstack` (SQS + Secrets Manager services enabled).
- Env templates: `.env.local.example`, `.env.qa.example`, `.env.prod.example` — templates only,
  committed; real `.env.local` is gitignored, real QA/PROD secrets live in AWS Secrets Manager
  only, never as files.
- `Makefile` with targets: `make up` (start Docker Compose), `make down`, `make test-local`
  (run pytest against the local stack), `make lint`, `make typecheck`.
- `README.md` documenting the above.

**Key files/directories:**
`pyproject.toml`, `docker-compose.yml`, `Makefile`, `.env.*.example`, `.gitignore`,
`.pre-commit-config.yaml`, `src/buybox/__init__.py`, `tests/__init__.py`.

**AWS resources touched:** none (local only).

**Testing approach:** `make up` brings up Postgres + LocalStack; `make test-local` runs a
trivial placeholder test to confirm pytest, the DB connection, and LocalStack are all reachable.
This phase's acceptance bar is "a developer can clone the repo and get a green test run with
one command and no manual AWS setup."

**Bootstrap prompt:**
> Implement Phase 0 of the Buy Box Engine described in `buy-box/architecture.md`: scaffold a
> Python (Poetry-managed) repo from scratch with this layout — `src/buybox/` for app code,
> `tests/` mirroring it, `infra/` reserved (empty, for later CDK code), `docs/`. Add
> `docker-compose.yml` with `postgres:16` and `localstack` (SQS + Secrets Manager) services.
> Add `.env.local.example`, `.env.qa.example`, `.env.prod.example` templates — never commit
> real secrets, gitignore `.env.local`. Add a `Makefile` with `up`, `down`, `test-local`,
> `lint`, `typecheck` targets. Configure `ruff` and `mypy` via pre-commit. Add a README
> explaining how to run `make up && make test-local`. No AWS deployment in this phase — local
> only. Non-negotiables for the whole project (apply here too): no secrets in git, Postgres
> must be the local stand-in for the same RDS Postgres used later in QA/PROD.

---

## Phase 1: Core domain model & ranking engine (pure Python, no AWS, no DB)

**Goal:** Build the actual product logic — the buy-box ranking algorithm — as a
framework-agnostic, infrastructure-free Python package. This is the core IP; it must be fully
unit-testable with nothing running (no Docker, no DB, no AWS).

**Depends on:** Phase 0 (repo layout, test tooling).

**Deliverables:**
- Data classes (e.g. `dataclasses` or `pydantic` models) for `Offer` (seller_id, listing_id,
  price, shipping_cost, shipping_speed_days, stock_qty, fulfillment_type, seller_rating,
  dispatch_time_hours, return_rate), `TenantRuleConfig` (per-tenant weights + eligibility
  thresholds), `RankingResult` (winning offer + per-offer scores + explanation).
- Eligibility filter step: excludes offers that fail hard constraints (out of stock, seller
  below minimum rating, price outside tolerance band, etc.) before scoring.
- Weighted scoring algorithm: configurable weights per signal (price, fulfillment speed,
  rating, dispatch time, return rate), normalized scores, deterministic tie-breaking rule.
- Explainability output: for any ranking result, produce a human-readable reason per offer
  ("lost: price 12% above lowest eligible offer" / "won: best weighted score 0.87").
- Unit tests covering: single eligible offer, no eligible offers, tie-breaking, each individual
  weight's effect on the outcome, and explanation text correctness.

**Key files/directories:**
`src/buybox/domain/models.py`, `src/buybox/domain/eligibility.py`,
`src/buybox/domain/ranking.py`, `src/buybox/domain/explain.py`, `tests/domain/`.

**AWS resources touched:** none.

**Testing approach:** `make test-local` (pytest only, no Docker services required for this
package — mark these tests so they can run with zero infrastructure at all, even faster than
the rest of the local suite).

**Bootstrap prompt:**
> Implement Phase 1 of the Buy Box Engine described in `buy-box/architecture.md`. Repo already
> has the Phase 0 layout (`src/buybox/`, `tests/`, Poetry, ruff/mypy via pre-commit). Build a
> framework-agnostic domain package at `src/buybox/domain/`: `Offer`, `TenantRuleConfig`, and
> `RankingResult` data models; an eligibility-filter step (stock, seller rating floor, price
> tolerance band); a weighted scoring/ranking function over price, shipping speed, seller
> rating, dispatch time, return rate, with configurable per-tenant weights and deterministic
> tie-breaking; and an explainability function producing a human-readable win/loss reason per
> offer. This package must have zero dependencies on AWS, a database, or any web framework —
> pure Python, fully unit-testable with pytest with no Docker/services running. Cover edge
> cases in tests: no eligible offers, ties, each weight's isolated effect. This is the core
> product IP, so favor clarity and correctness over cleverness.

---

## Phase 2: Persistence layer

**Goal:** Give the domain model durable storage, decoupled from the ranking logic via a
repository pattern, so the ranking engine never depends on SQLAlchemy or the DB directly.

**Depends on:** Phase 0 (Docker Postgres), Phase 1 (domain models to persist).

**Deliverables:**
- SQLAlchemy models: `tenants`, `offers`, `tenant_rule_configs` (versioned), `ranking_audit_log`
  (every ranking decision: inputs, winner, explanation, timestamp — this is both a debugging
  aid and the foundation for the Phase 8 seller-facing analytics).
- Alembic migrations, runnable against both local Docker Postgres and (later) real RDS.
- Repository classes (`OfferRepository`, `TenantConfigRepository`, `AuditLogRepository`)
  providing the only path between the domain layer and the DB — domain code in Phase 1 stays
  untouched.
- Integration tests running against the Dockerized Postgres from Phase 0, covering CRUD +
  migration up/down.

**Key files/directories:**
`src/buybox/persistence/models.py`, `src/buybox/persistence/repositories.py`,
`alembic/`, `tests/persistence/`.

**AWS resources touched:** none yet (still local Postgres; real RDS arrives in Phase 4).

**Testing approach:** `make test-local` runs these against the Docker Postgres service from
Phase 0. Migration tests must confirm both `alembic upgrade head` and `alembic downgrade -1`
work cleanly.

**Bootstrap prompt:**
> Implement Phase 2 of the Buy Box Engine described in `buy-box/architecture.md`. Repo has
> Phase 0 (Docker Postgres via docker-compose, Poetry, ruff/mypy) and Phase 1 (pure-Python
> domain models in `src/buybox/domain/`: `Offer`, `TenantRuleConfig`, `RankingResult`). Add a
> persistence layer at `src/buybox/persistence/`: SQLAlchemy models for `tenants`, `offers`,
> `tenant_rule_configs` (versioned — keep history, don't overwrite), and `ranking_audit_log`
> (record every ranking decision's inputs, winner, and explanation for later analytics). Add
> Alembic migrations. Add repository classes that are the *only* way the rest of the app
> touches the DB — the Phase 1 domain/ranking code must remain framework- and DB-agnostic and
> should not be modified to know about SQLAlchemy. Write integration tests against the local
> Dockerized Postgres from `docker-compose.yml`, including migration up/down correctness.

---

## Phase 3: API layer

**Goal:** Expose the ranking engine and tenant/config management over HTTP, in a form deployable
to Lambda (Phase 4) but fast to iterate on locally.

**Depends on:** Phase 1 (ranking logic), Phase 2 (persistence).

**Deliverables:**
- FastAPI app with routes: `POST /v1/tenants/{tenant_id}/rank` (given a listing's offers,
  return the ranking result + explanation), `GET/PUT /v1/tenants/{tenant_id}/config`
  (read/update rule weights), `GET /v1/tenants/{tenant_id}/audit-log` (paginated ranking
  history).
- Request/response schemas via Pydantic, matching the Phase 1 domain models.
- Auth stub: API-key header check per tenant (real secret storage wired in Phase 4; for now,
  read the key from local env/LocalStack Secrets Manager).
- Mangum wrapper (`src/buybox/api/lambda_handler.py`) so the same FastAPI app runs on Lambda
  unchanged; runs via `uvicorn src.buybox.api.app:app` locally.
- Contract tests per endpoint using FastAPI's `TestClient`, plus a smoke test running the app
  with `uvicorn` locally against the Dockerized Postgres end-to-end.

**Key files/directories:**
`src/buybox/api/app.py`, `src/buybox/api/routes/`, `src/buybox/api/lambda_handler.py`,
`src/buybox/api/schemas.py`, `tests/api/`.

**AWS resources touched:** none yet (Lambda deployment happens in Phase 4; this phase only adds
the Mangum-compatible handler).

**Testing approach:** `make test-local` runs FastAPI `TestClient` contract tests; a separate
`make run-local` target boots `uvicorn` against Docker Compose for manual/exploratory testing.

**Bootstrap prompt:**
> Implement Phase 3 of the Buy Box Engine described in `buy-box/architecture.md`. Repo has
> Phase 1 domain logic (`src/buybox/domain/`) and Phase 2 persistence
> (`src/buybox/persistence/`, repository pattern). Add a FastAPI app at `src/buybox/api/` with
> routes: rank offers for a tenant's listing, get/update a tenant's rule-weight config, and
> read a tenant's paginated ranking audit log. Use Pydantic schemas matching the Phase 1 domain
> models. Add a simple per-tenant API-key auth check (key lookup abstracted behind an interface
> so Phase 4 can swap in real AWS Secrets Manager without changing route code). Add a Mangum
> handler (`lambda_handler.py`) so this app is Lambda-deployable as-is later, while still
> runnable locally via `uvicorn`. Write FastAPI `TestClient` contract tests for every route.
> Do not modify the Phase 1 domain package's public interface — only call into it.

---

## Phase 4: AWS infrastructure as code (CDK)

**Goal:** Stand up real, secure, cost-controlled QA and PROD environments in AWS, deployable and
destroyable independently, so the app built in Phases 0–3 can actually run in the cloud.

**Depends on:** Phase 3 (the Lambda-ready API to deploy).

**Deliverables:**
- CDK app in Python at `infra/`, with two stages/stacks: `BuyBoxQaStack`, `BuyBoxProdStack`,
  sharing a common construct library (`infra/constructs/`) to avoid duplicating
  network/DB/Lambda definitions between them — differences expressed as stage parameters
  (instance size, Multi-AZ on/off, deletion protection on/off), not copy-pasted stacks.
- VPC with private subnets for RDS (no public DB access in either environment).
- RDS Postgres: QA = single-AZ, small instance (e.g. `db.t4g.micro`); PROD = Multi-AZ,
  deletion protection enabled, automated backups with point-in-time recovery enabled in both,
  but especially verified in PROD.
- Lambda function(s) running the Phase 3 API via the Mangum handler, fronted by API Gateway
  (HTTP API, cheaper than REST API).
- Secrets Manager entries for DB credentials and per-tenant API keys; Lambda IAM role scoped
  to only the specific secrets and DB it needs (least privilege, no wildcard resource ARNs).
- CloudWatch log groups for the Lambda with a sane retention period (cost control — don't
  default to "never expire").
- `cdk deploy --context stage=qa` / `--context stage=prod` as the deploy commands; `cdk diff`
  used before every deploy as a safety check.

**Key files/directories:**
`infra/app.py`, `infra/constructs/network.py`, `infra/constructs/database.py`,
`infra/constructs/api.py`, `infra/stacks/qa_stack.py`, `infra/stacks/prod_stack.py`,
`infra/cdk.json`.

**AWS resources touched:** VPC, RDS, Lambda, API Gateway, Secrets Manager, IAM, CloudWatch —
all real, in your paid AWS account. **Run `cdk diff` and review costs/resources before every
`cdk deploy`, and confirm with the user before the first deploy to each environment.**

**Testing approach:** `cdk synth` must succeed and be reviewed before any deploy. After
`cdk deploy --context stage=qa`, a smoke test hits the real QA API Gateway URL and confirms a
ranking request round-trips end-to-end against the real QA RDS instance. PROD deploy only
happens after QA smoke tests pass, and only with explicit manual confirmation given the real
cost/risk involved.

**Bootstrap prompt:**
> Implement Phase 4 of the Buy Box Engine described in `buy-box/architecture.md`. Repo has a
> Lambda-ready FastAPI app (`src/buybox/api/lambda_handler.py` via Mangum) from Phase 3. Build
> an AWS CDK (Python) app under `infra/` with a shared construct library
> (`infra/constructs/`: network, database, api) parameterized by stage, and two stacks —
> `BuyBoxQaStack` and `BuyBoxProdStack` — that both use those shared constructs with different
> parameters (QA: single-AZ small RDS instance, no deletion protection; PROD: Multi-AZ,
> deletion protection on, more conservative removal policies). VPC with private subnets for
> RDS — never publicly accessible. RDS credentials and per-tenant API keys in Secrets Manager;
> Lambda IAM role scoped to only the exact secrets/resources it needs, no wildcards. API
> Gateway HTTP API (not REST API, for cost) fronting the Lambda. CloudWatch log group with a
> bounded retention period. Do not run `cdk deploy` yourself — stop after `cdk synth` succeeds
> and describe exactly what `cdk diff` would create, so the human can review real AWS cost and
> resource creation before approving an actual deploy.

---

## Phase 5: Multi-tenancy & per-tenant rule config

**Goal:** Make the product genuinely sellable to multiple independent marketplace-operator
clients — hard tenant isolation and self-service config, not just a single-tenant deployment
with a `tenant_id` column bolted on.

**Depends on:** Phase 2 (persistence), Phase 3 (API), Phase 4 (real deployed environments to
harden).

**Deliverables:**
- Tenant isolation enforced at the repository layer (every query scoped by `tenant_id`; add a
  test that proves cross-tenant data leakage is impossible even with a malicious/incorrect
  query).
- Config versioning: updating a tenant's rule weights creates a new version row rather than
  overwriting, with the audit log (Phase 2) recording which config version was active for each
  ranking decision.
- Tenant onboarding flow: an admin-only endpoint (or CLI script for now — full admin UI is out
  of scope until there's a real second client) to create a tenant + issue its API key via
  Secrets Manager.
- Per-tenant rate limiting at the API Gateway layer (usage plans / throttling) so one tenant
  can't degrade service for another.

**Key files/directories:**
`src/buybox/persistence/repositories.py` (tenant-scoping enforcement),
`src/buybox/api/routes/admin.py`, `infra/constructs/api.py` (usage plans), `tests/multitenancy/`.

**AWS resources touched:** API Gateway usage plans/throttling (QA + PROD stacks updated).

**Testing approach:** Automated test that attempts (and fails) to read/write another tenant's
data through every repository method. Manual QA smoke test: onboard a second fake tenant,
confirm its config and data are fully isolated from the first.

**Bootstrap prompt:**
> Implement Phase 5 of the Buy Box Engine described in `buy-box/architecture.md`. Repo has
> Phase 2 persistence (repository pattern), Phase 3 API, and Phase 4 CDK-deployed QA/PROD
> environments. Harden multi-tenancy: audit every repository method in
> `src/buybox/persistence/repositories.py` to guarantee `tenant_id` scoping is impossible to
> bypass, and add tests that prove cross-tenant reads/writes fail even under adversarial
> inputs. Add config versioning so updating a tenant's rule weights creates a new version
> rather than overwriting the old one, and make sure the audit log records which config
> version was active for each ranking decision. Add an admin-only tenant-onboarding path
> (endpoint or CLI script) that creates a tenant and provisions its API key into Secrets
> Manager. Add per-tenant rate limiting via API Gateway usage plans in the Phase 4 CDK stacks.

---

## Phase 6: Event ingestion pipeline

**Goal:** Support real-time offer/inventory/price updates from a tenant's marketplace via
async events, rather than requiring every ranking call to carry full offer state — needed once
tenants have real traffic volume.

**Depends on:** Phase 4 (real AWS environments), Phase 5 (tenant isolation to scope events
correctly).

**Deliverables:**
- SQS queue (per environment) accepting offer/inventory update events; Lambda consumer that
  upserts into the Phase 2 offers table.
- Idempotent processing (dedupe by event ID) so redelivered SQS messages never double-apply.
- Dead-letter queue for events that fail processing after retries — this is a data-loss guard,
  not optional.
- Optional DynamoDB table (on-demand billing) caching the "current winner" per listing for fast
  reads, invalidated/refreshed whenever a relevant offer changes.
- Local equivalent via LocalStack SQS from Phase 0, so this pipeline is testable without touching
  real AWS.

**Key files/directories:**
`src/buybox/ingestion/consumer.py`, `src/buybox/ingestion/idempotency.py`,
`infra/constructs/ingestion.py` (queue + DLQ + consumer Lambda), `tests/ingestion/`.

**AWS resources touched:** SQS (+ DLQ), an additional Lambda, optionally DynamoDB — added to
QA/PROD stacks from Phase 4.

**Testing approach:** Local integration tests against LocalStack SQS covering normal
processing, duplicate delivery (idempotency), and forced failure → DLQ routing. QA smoke test
with a real event round-tripping through real SQS.

**Bootstrap prompt:**
> Implement Phase 6 of the Buy Box Engine described in `buy-box/architecture.md`. Repo has
> Phase 4 CDK stacks (QA/PROD in AWS) and Phase 5 tenant isolation. Add an event ingestion
> pipeline: an SQS queue (with a dead-letter queue — required, this is the data-loss guard) per
> environment, and a Lambda consumer that upserts offer/inventory updates into the existing
> offers table from Phase 2 via its repository (don't bypass the repository layer). Make
> processing idempotent by event ID so redelivered SQS messages never double-apply. Add an
> optional DynamoDB table (on-demand billing, not provisioned capacity, for cost) caching each
> listing's current winning offer, invalidated on relevant offer changes. Test locally against
> the LocalStack SQS service from `docker-compose.yml` (Phase 0) — cover normal processing,
> duplicate-delivery idempotency, and forced-failure-to-DLQ routing — before touching real AWS.

---

## Phase 7: CI/CD & per-environment test gates

**Goal:** Automate the path from commit to PROD with the right test gate at each step, so QA
and PROD stay independently verifiable and nothing reaches PROD without passing QA first.

**Depends on:** all prior phases (there's a full app + infra to gate by this point).

**Deliverables:**
- CI pipeline (GitHub Actions, adjust if a different CI is preferred): on every PR, run
  `make lint`, `make typecheck`, and unit tests (Phase 1, no infra needed) plus integration
  tests against Dockerized Postgres/LocalStack (Phases 2, 3, 6) — no real AWS touched by PRs.
- On merge to `main`: `cdk deploy --context stage=qa` automatically, followed by an automated
  QA smoke test suite hitting the real QA API.
- PROD deploy is a separate, manually-triggered workflow requiring the QA smoke tests to have
  passed on the exact commit being promoted, plus an explicit human approval step (GitHub
  Environments manual approval, or equivalent).
- Post-PROD-deploy: an automated synthetic canary (a scheduled Lambda or CI job hitting a
  cheap, safe endpoint every few minutes) to catch regressions immediately after deploy.

**Key files/directories:**
`.github/workflows/pr.yml`, `.github/workflows/deploy-qa.yml`,
`.github/workflows/deploy-prod.yml`, `tests/smoke/`.

**AWS resources touched:** none new — this phase only automates deploys of the Phase 4/6
resources, plus adds a small canary Lambda.

**Testing approach:** The pipeline itself is the test — verify by opening a throwaway PR and
confirming lint/typecheck/unit/integration all run and block merge on failure; verify QA
auto-deploy and smoke test on a merge to `main`; verify PROD deploy requires manual approval
and fails closed if QA smoke tests didn't pass first.

**Bootstrap prompt:**
> Implement Phase 7 of the Buy Box Engine described in `buy-box/architecture.md`. Repo has the
> full app (Phases 0–3), CDK infra for QA/PROD (Phase 4), multi-tenancy (Phase 5), and event
> ingestion (Phase 6). Add GitHub Actions workflows: on every PR run lint, typecheck, unit
> tests (no infra), and integration tests against Docker Compose Postgres/LocalStack — real AWS
> must never be touched by PR runs. On merge to `main`, auto-deploy to QA via CDK and run an
> automated smoke-test suite against the real QA API. Add a separate, manually-triggered PROD
> deploy workflow that only allows promoting a commit whose QA smoke tests already passed, and
> requires an explicit human approval step before running `cdk deploy --context stage=prod`.
> After PROD deploy, add a small scheduled canary check hitting a safe read-only endpoint every
> few minutes to catch regressions immediately.

---

## Phase 8: Observability & security hardening pass

**Goal:** Close the gap between "it works" and "it's safe to run someone else's production
traffic through it" — this is the phase that makes the product trustworthy to paying tenants.

**Depends on:** Phase 4 (infra to instrument), Phase 7 (pipeline to enforce checks going
forward).

**Deliverables:**
- Structured logging (JSON logs) throughout the API and ingestion Lambdas, with tenant_id and
  request_id on every log line for traceability.
- CloudWatch dashboards + alarms: error rate, p99 latency, DLQ depth (from Phase 6), RDS
  connection count/CPU — alarms wired to a notification target (email/SNS at minimum).
- WAF attached to the PROD API Gateway (basic managed rule sets — rate limiting, common
  exploit patterns) — QA can skip WAF to keep costs down, but PROD should not be public without
  it.
- Verification (not just configuration) that PROD RDS automated backups and point-in-time
  recovery actually work: perform and document a real restore-to-a-point-in-time test.
- IAM policy review pass across every Lambda role created in Phases 4–6, confirming no
  wildcard resource ARNs remain.
- Secrets rotation configured for DB credentials in Secrets Manager (RDS supports managed
  rotation).

**Key files/directories:**
`infra/constructs/observability.py`, `infra/constructs/waf.py`, `docs/runbooks/backup-restore-test.md`.

**AWS resources touched:** CloudWatch alarms/dashboards, WAF, Secrets Manager rotation config —
added to the Phase 4 stacks.

**Testing approach:** Trigger a deliberate failure (e.g. bad request causing a 500) and confirm
it shows up in the dashboard/alarm. Actually perform the RDS point-in-time restore test in QA
(never test destructive recovery procedures against PROD directly) and document the steps and
result in `docs/runbooks/`.

**Bootstrap prompt:**
> Implement Phase 8 of the Buy Box Engine described in `buy-box/architecture.md`. Repo has
> deployed QA/PROD infra (Phase 4), CI/CD (Phase 7). Add structured JSON logging with
> tenant_id/request_id on every log line across the API and ingestion Lambdas. Add CloudWatch
> dashboards and alarms for error rate, p99 latency, DLQ depth, and RDS CPU/connections, wired
> to an SNS topic for notifications. Attach AWS WAF managed rule sets to the PROD API Gateway
> only (skip WAF in QA to control cost). Review every IAM role created so far and eliminate any
> wildcard resource ARNs. Configure Secrets Manager automated rotation for RDS credentials.
> Then, in the QA environment only (never PROD), actually perform and document a point-in-time
> restore test for RDS, writing the procedure and result to
> `docs/runbooks/backup-restore-test.md`.

---

## Phase 9 (stretch): Seller-facing upsell module

**Goal:** Once the core engine has at least one real paying marketplace-operator tenant, add a
seller-facing layer (dashboards showing sellers why they won/lost the buy box and what to
change) as an additional revenue line — either white-labeled for the tenant or sold directly.

**Depends on:** a real tenant using Phases 0–8 in production; do not build this speculatively.

**Deliverables:** to be scoped in a follow-up architecture doc once reached — likely a
separate frontend app consuming the existing ranking/audit-log API (Phase 3), no changes to
the core engine required beyond possibly new read-only aggregation endpoints.

**Bootstrap prompt:** (write when this phase is actually reached, informed by real tenant
feedback — premature to fully specify now).

---

## Verification of this document

- Sanity-check by pasting the Phase 0 bootstrap prompt into a fresh Claude session and
  confirming it scaffolds the repo without needing to ask for missing context.
- Each phase's own "Testing approach" section is that phase's acceptance bar once implemented.
