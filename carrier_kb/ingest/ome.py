from __future__ import annotations

import psycopg

from carrier_kb.ingest.adapters import CapturedRecord
from carrier_kb.ingest.registry import SourceDefinition


class OmeTranscriptAdapter:
    """Read-only adapter for OME's recruiter voice transcripts."""

    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("OME_ANALYTICS_DSN is required")
        self.dsn = dsn

    async def capture(self, source: SourceDefinition) -> list[CapturedRecord]:
        async with await psycopg.AsyncConnection.connect(self.dsn) as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT v.call_record_id, v.case_key, v.transcript_text,
                       v.created_at, c.direction, c.duration_s, c.source_system,
                       c.started_at, e.conversion_outcome, e.risk_level, e.overall_score
                FROM public.recruiter_voice_transcript v
                LEFT JOIN public.recruiter_call c ON c.call_id = v.call_record_id
                LEFT JOIN LATERAL (
                    SELECT conversion_outcome, risk_level, overall_score
                    FROM public.recruiter_evaluations
                    WHERE call_record_id = v.call_record_id
                    ORDER BY created_at DESC NULLS LAST
                    LIMIT 1
                ) e ON true
                WHERE v.transcript_text IS NOT NULL AND btrim(v.transcript_text) <> ''
                ORDER BY v.created_at DESC NULLS LAST
                LIMIT 10000
                """
            )
            rows = await cursor.fetchall()
        return [
            CapturedRecord(
                native_id=str(call_id),
                body=transcript,
                source_url=None,
                occurred_at=started_at or created_at,
                metadata={
                    "case_key": case_key or "unknown",
                    "direction": direction or "unknown",
                    "duration_seconds": float(duration) if duration is not None else None,
                    "source_system": source_system or "unknown",
                    "conversion_outcome": conversion_outcome or "unknown",
                    "risk_level": risk_level or "unknown",
                    "overall_score": float(overall_score) if overall_score is not None else None,
                    "historical": True,
                },
            )
            for call_id, case_key, transcript, created_at, direction, duration, source_system,
            started_at, conversion_outcome, risk_level, overall_score in rows
            if call_id and created_at
        ]
