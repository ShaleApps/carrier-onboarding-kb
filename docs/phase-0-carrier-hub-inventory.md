# Phase 0: Carrier Hub inventory

Status: initial code-backed inventory; no production data was copied into this repository.

Reviewed sources:

- `carrier-onboarding-server/proto/v1/carrier-onboarding-service.proto`
- `carrier-onboarding-server/proto/v1/read_requests.proto`
- `carrier-onboarding-server/doc/bainbridge-onboarding-current-state.md`
- `carrier-onboarding-server/doc/cron.md`
- `carrier-onboarding-web/src/lib/client.ts`
- `carrier-onboarding-web/src/components/public/public-application-status.tsx`
- Front message export and OME recruiter-call transcript samples reviewed separately

## Product boundary

Carrier Hub is the operational system of record for the onboarding application,
verification state, company/driver linkage, public status page, and carrier
self-service. The KB should explain those facts and policies; it should not
reimplement the state machine or write directly to Carrier Hub tables.

The server has a dedicated Postgres database, Redis-backed/background jobs, and
integrations with LoHi, RMIS, Evident/BRS, DocuSign, Tenstreet, Workday, and
campaign/outreach systems. It supports multiple brokerages, including LoHi,
Bainbridge, Candlestick, and Red Rocks, so requirements must always be
brokerage- and program-scoped.

## Canonical read model

| Domain | Important facts exposed | KB treatment |
|---|---|---|
| Identity | Firebase user, roles/permissions, carrier-admin company/application resolution | Authentication and authorization only; never index as generic text |
| Lead | Carrier/contact identity, DOT/MC/authority, work area, market, brokerage, notes, lead status | Internal entity context; public responses expose only verified, carrier-scoped fields |
| Application | Lifecycle status, timestamps, assigned manager, company/driver IDs, errors, archive state | Canonical live context; answer “where am I?” and “what happens next?” |
| RMIS | Invitation/submission/certification state, carrier ID, reminders, retry/escalation state | Read-only compliance context; do not expose internal vendor/error detail by default |
| Evident/BRS | Background verification, attributes, BRS compliance, timestamps, diagnostics | Explain required action and state; keep adverse/internal reasoning privileged |
| Agreement | DocuSign status, signing link, reminders (Bainbridge) | Public: whether action is needed; internal: operational detail |
| Training/gates | Training videos, Tenstreet, Safeland/PEC, W-9, H2S requirements and completion | Public checklist and next step; applicability must be computed by Carrier Hub |
| Grace/holds | RMIS/BRS deadlines, manual grants, load-booking holds, suspension/reinstatement state | Internal-only operational context; never infer from stale documents |
| Banking/payment | Carrier/factoring banking status, approval documents, Workday status | Highly restricted internal tool result; never put raw account values in the KB |
| Documents | Carrier uploads, COI/factoring approval documents, signed download URLs | Return secure action/link from Carrier Hub, not indexed document contents by default |
| Markets | Public market catalog; lead-assigned markets and counts | General market guidance can be public; live availability requires a separate source |
| Drivers | Invited/assigned/accepted/declined drivers and certification attestations | Carrier-scoped status; mutations require explicit gated actions |
| Outreach | Leads, imports, campaigns, recipients, send logs | Internal recruiting operations; not part of public onboarding answers |

## Lifecycle and state model

The effective flow is:

1. A lead is captured (often outside Carrier Hub from MyCarrierPackets, Front,
   or an operator workflow).
2. Carrier Hub creates an application and starts the applicable vendor checks.
3. RMIS, Evident/background, BRS, DocuSign, Tenstreet, and training facts are
   updated by webhooks and scheduled reconciliation jobs.
4. Brokerage-specific creation gates determine whether a LoHi company and
   driver can be created.
5. Separate jobs attach downstream identifiers such as Workday, NetSuite
   (legacy paths), and First Hitch.
6. Post-activation grace/hold rules may restrict load booking and later restore
   it when requirements recover.

The KB should not flatten this into a single status string. It needs a derived
`next_action` view containing:

- current stage and human-readable explanation;
- blocking requirements and their evidence state;
- required action, actor, and secure destination;
- deadline or freshness timestamp, when applicable;
- whether the fact is authoritative, configuration-dependent, or pending human review.

## Read-only endpoint groups to integrate later

The first live tool contract should be deliberately small:

- `GET /api/v1/user_info` — resolve authenticated internal or carrier-admin scope.
- `GET /api/v1/application/{id}` — internal application detail.
- `GET /api/v1/application/{id}/status` — public-safe status projection.
- `GET /api/v1/lead/{leadId}/pre_vetting_status` — only if the projection is
  approved for the caller.
- `GET /api/v1/carrier-documents` — metadata only, with signed download URLs
  generated by Carrier Hub when explicitly requested.
- `GET /api/v1/markets` — public catalog.
- `GET /api/v1/lead-markets` — internal operational market usage.
- `GET /api/v1/application/{applicationId}/driver-invitations` and the public
  equivalent — carrier-scoped driver status.
- Narrow future `/api/v1/kb-context/...` projections — preferred over passing
  the full application object to the model.

All write, reminder, resend, approval, suspension, grace, banking, campaign,
and driver-invite mutation endpoints are out of scope for the first KB release.

## Public versus internal answer surface

### Public carrier answers

- What documents, insurance, authority, and training are required?
- What is my current application step?
- Which item is missing or still processing?
- How do I upload evidence, sign the agreement, complete training, or invite a driver?
- What do payment, factoring, toll, equipment, and load terms mean when backed by
  an approved public policy source?
- What should I do next, and how do I contact a human?

Public answers must be limited to the caller's verified application capability
and the `carrier_public` corpus. They must never reveal internal notes, raw
vendor payloads, banking values, internal rejection reasons, other carriers,
or unrestricted market/earnings data.

### Internal answers

- Why is an application blocked, pending, suspended, or escalated?
- Which vendor check, grace rule, or configuration flag is governing the result?
- What is the complete timeline and who owns the next action?
- Which Front conversation, workflow, transcript, or policy document supports the answer?
- What is the correct escalation route?

Internal answers can use `carrier_internal`, but sensitive fields should be
returned through typed tool results with field-level authorization rather than
indexed into broad text retrieval.

## Source authority and ingestion policy

| Source | Use | Authority |
|---|---|---|
| Carrier Hub typed projections | Personalized status, next action, document/driver state | Highest; live and scoped |
| Approved Drive policy guides | Requirements, instructions, payment/program explanations | Canonical after owner review and effective dating |
| Active Maverick workflow definitions | Decision logic, gates, integrations, escalation behavior | Internal reference; only published workflows with recent runs qualify as active |
| Front messages | Real question taxonomy, approved response examples, escalation patterns | Historical/contextual; deduplicate segments and exclude campaigns/receipts |
| OME call transcripts | Discovery of carrier objections and vocabulary | Internal research/evaluation; not a public answer source |
| Slack | Internal exceptions and operational decisions | Allowlist-only, internal, with owner and expiry |
| LoHi/OME views | Structured operational facts and aggregates | Named read-only views only; no model-authored SQL |

Front analysis found recurring questions about power-only loads, lanes and
availability, packets/COIs/RMIS, training and portal setup, direct payment,
factoring, trailer fees, tolls, and operational exceptions. These should become
the initial evaluation taxonomy, not an automatic import of historical replies.

## Gaps in the current KB scaffold

The existing scaffold has the right corpus and authorization boundary, but it
still needs:

1. a question router separating policy, live status, market, exception, and escalation queries;
2. a typed Carrier Hub context client and a minimal `/kb-context` contract;
3. canonical claims/rules with owner, brokerage, market, effective dates, and supersession;
4. entity- and application-scoped access checks, including field-level redaction;
5. separate historical/research indexes for Front and OME;
6. ingestion quality controls for deduplication, PII minimization, source authority,
   deletion/revocation, and freshness;
7. a labeled evaluation set built from real Front and transcript questions;
8. audit records for the question, identity scope, tools, sources, freshness, and handoff.

## Phase 0 exit criteria

- Carrier Hub fields and lifecycle transitions are mapped to a reviewed typed model.
- Public-safe and internal-only projections are explicitly defined.
- The first 20–40 recurring question patterns have expected sources and escalation behavior.
- At least one representative answer is tested for each major category: requirements,
  status, verification, training, payment, market/opportunity, driver, exception,
  and escalation.
- Source owners, refresh cadence, effective dates, and revocation behavior are recorded.
- No live write action or broad database credential is required by the KB.
