-- OME Analytics co-location migration. All KB state is isolated in its own schema.
CREATE SCHEMA IF NOT EXISTS carrier_kb;

DO $$ BEGIN
  CREATE TYPE carrier_kb.kb_corpus AS ENUM ('carrier_public', 'carrier_internal');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS carrier_kb.sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  registry_id text NOT NULL,
  corpus carrier_kb.kb_corpus NOT NULL,
  native_id text NOT NULL,
  title text NOT NULL,
  source_url text,
  occurred_at timestamptz NOT NULL,
  content_hash text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}',
  ingested_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (registry_id, native_id)
);

CREATE TABLE IF NOT EXISTS carrier_kb.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  corpus carrier_kb.kb_corpus NOT NULL,
  body text NOT NULL,
  content_hash text NOT NULL,
  body_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
  embedding double precision[],
  valid_from timestamptz NOT NULL DEFAULT now(),
  valid_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS documents_corpus_content_hash_idx
  ON carrier_kb.documents (corpus, content_hash);

CREATE TABLE IF NOT EXISTS carrier_kb.document_sources (
  document_id uuid NOT NULL REFERENCES carrier_kb.documents(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES carrier_kb.sources(id) ON DELETE CASCADE,
  PRIMARY KEY (document_id, source_id)
);

CREATE INDEX IF NOT EXISTS documents_corpus_fts_idx ON carrier_kb.documents USING gin (body_tsv);
CREATE INDEX IF NOT EXISTS sources_corpus_occurred_idx ON carrier_kb.sources (corpus, occurred_at DESC);
