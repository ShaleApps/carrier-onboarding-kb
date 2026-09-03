from __future__ import annotations

import hashlib

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from carrier_kb.ingest.adapters import CapturedRecord
from carrier_kb.ingest.registry import SourceDefinition


class PostgresIngestWriter:
    """Writes only captured records from an explicitly approved source."""

    def __init__(self, dsn: str, schema: str = "carrier_kb"):
        if not dsn:
            raise ValueError("KB DSN is required")
        self.dsn = dsn
        if not schema.replace("_", "").isalnum():
            raise ValueError("invalid KB schema")
        self.schema = schema

    async def write(self, source: SourceDefinition, records: list[CapturedRecord]) -> int:
        async with await psycopg.AsyncConnection.connect(self.dsn) as connection:
            run_id = await self._start_run(connection, source, len(records))
            await connection.commit()
            try:
                async with connection.cursor() as cursor:
                    for record in records:
                        content_hash = hashlib.sha256(record.body.encode()).hexdigest()
                        await cursor.execute(sql.SQL("""
                        INSERT INTO {schema}.sources (registry_id, corpus, native_id, title, source_url,
                                             occurred_at, content_hash, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (registry_id, native_id) DO UPDATE SET
                          corpus = EXCLUDED.corpus, title = EXCLUDED.title,
                          source_url = EXCLUDED.source_url, occurred_at = EXCLUDED.occurred_at,
                          content_hash = EXCLUDED.content_hash, metadata = EXCLUDED.metadata,
                          valid_until = NULL
                        RETURNING id
                        """).format(schema=sql.Identifier(self.schema)),
                        (source.id, source.corpus.value, record.native_id, source.id,
                         record.source_url, record.occurred_at, content_hash, Jsonb(record.metadata)),
                        )
                        source_id = (await cursor.fetchone())[0]
                        await cursor.execute(sql.SQL("""
                        INSERT INTO {schema}.documents (corpus, body, content_hash)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (corpus, content_hash) DO UPDATE SET
                          body = EXCLUDED.body, valid_until = NULL
                        RETURNING id
                        """).format(schema=sql.Identifier(self.schema)),
                        (source.corpus.value, record.body, content_hash),
                        )
                        document_id = (await cursor.fetchone())[0]
                        await cursor.execute(
                        sql.SQL("DELETE FROM {schema}.document_sources WHERE source_id = %s").format(schema=sql.Identifier(self.schema)),
                        (source_id,),
                        )
                        await cursor.execute(
                        sql.SQL("INSERT INTO {schema}.document_sources (document_id, source_id) VALUES (%s, %s)").format(schema=sql.Identifier(self.schema)),
                        (document_id, source_id),
                        )
                if records:
                    await self._retire_missing_records(connection, source.id, [record.native_id for record in records])
                await self._finish_run(connection, run_id, "succeeded", len(records))
                await connection.commit()
            except Exception as exc:
                await connection.rollback()
                await self._finish_run(connection, run_id, "failed", 0, type(exc).__name__)
                await connection.commit()
                raise
        return len(records)

    async def _retire_missing_records(self, connection, registry_id: str, native_ids: list[str]) -> None:
        """Retire records absent from a non-empty complete-source snapshot.

        Empty captures intentionally do not retire a source: an upstream outage
        must never be interpreted as a deletion signal.
        """
        async with connection.cursor() as cursor:
            await cursor.execute(
                sql.SQL("""
                    UPDATE {schema}.sources
                    SET valid_until = now()
                    WHERE registry_id = %s
                      AND valid_until IS NULL
                      AND NOT (native_id = ANY(%s))
                """).format(schema=sql.Identifier(self.schema)),
                (registry_id, native_ids),
            )
            await cursor.execute(
                sql.SQL("""
                    UPDATE {schema}.documents d
                    SET valid_until = now()
                    WHERE d.valid_until IS NULL
                      AND NOT EXISTS (
                        SELECT 1
                        FROM {schema}.document_sources ds
                        JOIN {schema}.sources s ON s.id = ds.source_id
                        WHERE ds.document_id = d.id AND s.valid_until IS NULL
                      )
                """).format(schema=sql.Identifier(self.schema)),
            )

    async def _start_run(self, connection, source: SourceDefinition, records_seen: int):
        async with connection.cursor() as cursor:
            await cursor.execute(
                sql.SQL("""
                    INSERT INTO {schema}.ingestion_runs (registry_id, status, records_seen, metadata)
                    VALUES (%s, 'running', %s, %s)
                    RETURNING id
                """).format(schema=sql.Identifier(self.schema)),
                (source.id, records_seen, Jsonb({"kind": source.kind, "corpus": source.corpus.value})),
            )
            return (await cursor.fetchone())[0]

    async def _finish_run(self, connection, run_id, status: str, records_written: int, error_message: str | None = None):
        async with connection.cursor() as cursor:
            await cursor.execute(
                sql.SQL("""
                    UPDATE {schema}.ingestion_runs
                    SET status = %s, finished_at = now(), records_written = %s, error_message = %s
                    WHERE id = %s
                """).format(schema=sql.Identifier(self.schema)),
                (status, records_written, error_message, run_id),
            )
