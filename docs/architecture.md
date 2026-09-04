# Architecture

Carrier Hub remains the operational system of record. This service stores only knowledge-ready representations and citations, never becomes an onboarding workflow writer, and starts with no write API.

## Boundaries

| Concern | Owner |
|---|---|
| Identity, roles, applications, enrollment links | Carrier Hub |
| Source selection, capture, distillation, retrieval, citations | Carrier Onboarding KB |
| Drive/Slack access grants and content ownership | Source owners |
| Live status/requirement explanation | Carrier Hub read-only, application-scoped status tool |

`carrier_public` and `carrier_internal` are separate corpus values applied to both sources and documents. The API derives allowed corpora from an authenticated principal; callers and models cannot select one.

## Ingestion

Each configured source is allowlisted and has an owner, cadence, corpus, and source-specific selector. Capture is lossless and idempotent on `(registry_id, native_id)`. A later worker will normalize and distill captures into documents with source links. LoHi ingestion reads only approved database views/dossiers using a read-only account.

## Retrieval

The current repository performs PostgreSQL full-text retrieval within the allowed
corpora and returns evidence/citations to the answer layer. It must return no
result rather than widen scope. Vector retrieval is intentionally deferred: the
OME Analytics instance does not currently provide `pgvector`, and lexical
retrieval gives a simple, auditable first production slice. The answer layer
must cite every material claim and hand off on weak evidence.

For a verified application capability, the answer layer may prepend a
public-safe, read-only Carrier Hub status projection. This is live operational
context, not indexed KB content, and it does not alter corpus authorization.
