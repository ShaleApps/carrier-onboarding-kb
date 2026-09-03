ALTER TABLE sources ADD COLUMN IF NOT EXISTS valid_until timestamptz;
CREATE INDEX IF NOT EXISTS sources_registry_active_idx
  ON sources (registry_id) WHERE valid_until IS NULL;
