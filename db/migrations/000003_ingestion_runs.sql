-- Local Docker compatibility for KB_SCHEMA=public.
CREATE TABLE IF NOT EXISTS ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  registry_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  records_seen integer NOT NULL DEFAULT 0 CHECK (records_seen >= 0),
  records_written integer NOT NULL DEFAULT 0 CHECK (records_written >= 0),
  error_message text,
  metadata jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ingestion_runs_registry_started_idx
  ON ingestion_runs (registry_id, started_at DESC);
