from __future__ import annotations

import psycopg

from carrier_kb.ingest.adapters import CapturedRecord
from carrier_kb.ingest.registry import SourceDefinition


class OmeTranscriptAdapter:
    """Read-only adapter for the approved OME voice-call transcript table."""

    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("OME_ANALYTICS_DSN is required")
        self.dsn = dsn

    async def capture(self, source: SourceDefinition) -> list[CapturedRecord]:
        async with await psycopg.AsyncConnection.connect(self.dsn) as connection, connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT call_id, call_type, transcript, called_at
                    FROM nucor.voice_calls
                    WHERE transcript IS NOT NULL AND btrim(transcript) <> ''
                    ORDER BY called_at DESC NULLS LAST
                    LIMIT 10000
                    """
                )
                rows = await cursor.fetchall()
        return [
            CapturedRecord(
                native_id=str(call_id),
                body=transcript,
                source_url=None,
                occurred_at=called_at,
                metadata={"call_type": call_type or "unknown", "historical": True},
            )
            for call_id, call_type, transcript, called_at in rows
            if call_id and called_at
        ]
