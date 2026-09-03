from __future__ import annotations

import hashlib

import psycopg
from psycopg.types.json import Jsonb

from carrier_kb.ingest.adapters import CapturedRecord
from carrier_kb.ingest.registry import SourceDefinition


class PostgresIngestWriter:
    """Writes only captured records from an explicitly approved source."""

    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("KB DSN is required")
        self.dsn = dsn

    async def write(self, source: SourceDefinition, records: list[CapturedRecord]) -> int:
        async with await psycopg.AsyncConnection.connect(self.dsn) as connection:
            async with connection.cursor() as cursor:
                for record in records:
                    content_hash = hashlib.sha256(record.body.encode()).hexdigest()
                    await cursor.execute(
                        """
                        INSERT INTO sources (registry_id, corpus, native_id, title, source_url,
                                             occurred_at, content_hash, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (registry_id, native_id) DO UPDATE SET
                          corpus = EXCLUDED.corpus, title = EXCLUDED.title,
                          source_url = EXCLUDED.source_url, occurred_at = EXCLUDED.occurred_at,
                          content_hash = EXCLUDED.content_hash, metadata = EXCLUDED.metadata
                        RETURNING id
                        """,
                        (source.id, source.corpus.value, record.native_id, source.id,
                         record.source_url, record.occurred_at, content_hash, Jsonb(record.metadata)),
                    )
                    source_id = (await cursor.fetchone())[0]
                    await cursor.execute(
                        """
                        INSERT INTO documents (corpus, body, content_hash)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (corpus, content_hash) DO UPDATE SET body = EXCLUDED.body
                        RETURNING id
                        """,
                        (source.corpus.value, record.body, content_hash),
                    )
                    document_id = (await cursor.fetchone())[0]
                    await cursor.execute(
                        "DELETE FROM document_sources WHERE source_id = %s",
                        (source_id,),
                    )
                    await cursor.execute(
                        "INSERT INTO document_sources (document_id, source_id) VALUES (%s, %s)",
                        (document_id, source_id),
                    )
            await connection.commit()
        return len(records)
