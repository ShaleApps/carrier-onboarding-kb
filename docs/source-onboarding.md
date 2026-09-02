# Source onboarding checklist

1. Name the questions this source is allowed to answer and designate an owner.
2. Choose `carrier_public` only when every included record is appropriate for an external carrier. Otherwise use `carrier_internal`.
3. Add exact Drive IDs, Slack channel IDs, or a migration-owned LoHi view to the registry. Wildcards and workspace search are prohibited.
4. Grant the least-privileged service identity access, configure it outside Git, and run a dry capture.
5. Add representative questions and expected citations to the evaluation set before enabling scheduled ingestion.
6. Review freshness, revocation, and deletion behavior with the source owner.
