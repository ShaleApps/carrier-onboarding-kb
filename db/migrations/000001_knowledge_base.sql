CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE kb_corpus AS ENUM ('carrier_public', 'carrier_internal');

CREATE TABLE sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  registry_id text NOT NULL,
  corpus kb_corpus NOT NULL,
  native_id text NOT NULL,
  title text NOT NULL,
  source_url text,
  occurred_at timestamptz NOT NULL,
  content_hash text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}',
  ingested_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (registry_id, native_id)
);

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  corpus kb_corpus NOT NULL,
  body text NOT NULL,
  content_hash text NOT NULL,
  body_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
  embedding vector(1536),
  valid_from timestamptz NOT NULL DEFAULT now(),
  valid_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX documents_corpus_content_hash_idx ON documents (corpus, content_hash);

CREATE TABLE document_sources (
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  PRIMARY KEY (document_id, source_id)
);

CREATE INDEX documents_corpus_fts_idx ON documents USING gin (body_tsv);
CREATE INDEX documents_corpus_embedding_idx ON documents USING hnsw (embedding vector_cosine_ops);
CREATE INDEX sources_corpus_occurred_idx ON sources (corpus, occurred_at DESC);
