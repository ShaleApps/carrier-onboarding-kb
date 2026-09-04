# Carrier Onboarding KB

Backend knowledge service for Carrier Hub. It answers carrier-onboarding questions from deliberately approved sources, with citations and a hard boundary between carrier-safe and internal knowledge.

This is **not** a general company search service and it never receives direct browser credentials. Carrier Hub is the identity and workflow authority; this service is the retrieval and answer authority.

## First slice

- Two physical corpora: `carrier_public` and `carrier_internal`.
- Source registry with explicit Google Drive files/folders, Slack channels, and LoHi read-only dossiers/views.
- Read-only ingest adapters and a provenance-preserving Postgres schema.
- Carrier Hub identity adapter for internal Firebase sessions and a short-lived capability-token lane for public enrollment pages.
- Cited corpus-scoped retrieval API plus a read-only, public-safe Carrier Hub application-status card when a verified capability includes an application ID.

## Run locally

```bash
uv sync --group dev
cp .env.example .env
uv run uvicorn carrier_kb.api.app:create_app --factory --reload
uv run pytest
```

### Local database

Start the isolated development database (Docker Desktop must be running):

```bash
docker compose up -d kb-postgres
cp .env.example .env
uv run carrier-kb-ingest --registry config/sources.yaml
```

The compose file uses port `55432` and a development-only password. Never use
these credentials for a shared or production deployment.

`config/sources.example.yaml` is a checked-in example only. Copy it to an untracked file and replace the placeholder IDs after a source-owner and visibility review.

### Production bootstrap

The container includes `config/sources.production.yaml`, which contains only
the two reviewed static evidence packs. After the OME runtime role is provisioned,
seed a new environment once with:

```bash
carrier-kb-ingest --registry /app/config/sources.production.yaml
```

External Drive, Slack, Front, and OME sources must be added only after their
allowlist, credentials, and evaluation coverage are approved.

## Core rules

1. A carrier-facing request searches only `carrier_public`; internal requests may search both corpora.
2. Visibility is assigned at ingest and enforced in SQL. We do not retrieve internal text and redact it afterward.
3. Slack and Drive are allowlist-only. LoHi access is through named read-only views/dossiers, never model-authored SQL.
4. Every answer includes the sources used. When evidence is weak, the service declines and hands off rather than inventing an answer.

See [docs/architecture.md](docs/architecture.md), [docs/carrier-hub-contract.md](docs/carrier-hub-contract.md), and [docs/source-onboarding.md](docs/source-onboarding.md).
