# Retrieval baseline (2026-09-03)

The 18-question evaluation currently passes **13/18** after ingesting the
canonical evidence pack.

## Failures and disposition

| Question | Finding | Correct next action |
|---|---|---|
| W-9 submission | No approved W-9 evidence is present in the current corpus. | Obtain canonical policy; do not infer. |
| Application status | Carrier Hub provides live status, but the lexical check expects `application` in retrieved text. | Replace the check with a structured live-context assertion. |
| Onboarding steps | Evidence exists, but the query is not reliably ranking the pack. | Improve retrieval/query expansion. |
| Bonus eligibility | Canonical evidence uses requirements/milestones rather than the literal word `eligible`. | Use intent-level evaluation and preserve dynamic-term caveat. |
| Broker value | Halliburton rationale exists, but falls outside the top eight results. | Improve ranking or add a dedicated canonical topic chunk. |
| Human support | Escalation guidance exists, but does not contain the literal `contact` term. | Use semantic/intent checks rather than token presence. |

The baseline is deliberately not “fixed” by adding unsupported W-9 policy or
loosening the source boundary. Human confirmation remains required for the
conflicting authority, training, factoring, and dynamic bonus rules.
