# OME Analytics co-location rollout

This service can use OME Analytics as its only database by setting:

```text
KB_DSN=<OME Analytics DSN>
KB_SCHEMA=carrier_kb
```

## DBA steps

1. Review and apply `db/migrations/000002_carrier_kb_schema.sql` with the OME
   migration process. This creates only the `carrier_kb` schema and tables.
2. Create a dedicated login role (for example `carrier_kb_runtime`) through the
   organization’s normal secret-management process. Do not use the shared
   `postgres` role.
3. Grant the runtime role only:

```sql
GRANT USAGE ON SCHEMA carrier_kb TO carrier_kb_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA carrier_kb TO carrier_kb_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA carrier_kb TO carrier_kb_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA carrier_kb
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO carrier_kb_runtime;
```

4. Grant read-only access to explicitly approved source tables/views only. The
   initial OME transcript adapter requires `public.recruiter_voice_transcript`
   and optionally `public.recruiter_call` and `public.recruiter_evaluations`.
5. Do not grant access to unrelated OME schemas such as `ap`, `boston_beer`, or
   `dwyeromega`.
6. Store the role DSN as a Kubernetes Secret/ExternalSecret; never commit it.

## Validation

Run the migration, then verify using the runtime role:

```sql
SELECT current_user, current_database();
SELECT to_regclass('carrier_kb.sources'), to_regclass('carrier_kb.documents');
SELECT has_schema_privilege(current_user, 'carrier_kb', 'USAGE');
```

The runtime role should be able to read/write `carrier_kb` and read only the
approved source relations. It should not be able to create extensions, alter
OME-owned tables, or read unrelated department schemas.

The application can then run with the existing container/deployment pattern;
no second Postgres instance is required.
