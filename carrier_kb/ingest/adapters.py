"""Read-only source adapters. They emit source records; only the ingestion service writes KB rows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from carrier_kb.ingest.registry import SourceDefinition


@dataclass(frozen=True)
class CapturedRecord:
    native_id: str
    body: str
    source_url: str | None
    occurred_at: datetime
    metadata: dict


class SourceAdapter:
    async def capture(self, source: SourceDefinition) -> list[CapturedRecord]:
        raise NotImplementedError


class GoogleDriveAdapter(SourceAdapter):
    """Fetches only registry file IDs via Docs/Drive APIs; folder-wide discovery is intentionally absent."""
    async def capture(self, source: SourceDefinition) -> list[CapturedRecord]:
        # Wire Google credentials/client here after granting the service account access to exact files.
        raise NotImplementedError("Google Drive adapter requires approved service-account configuration")


class SlackAdapter(SourceAdapter):
    """Fetches only registry channel IDs. Slack search is prohibited because it bypasses the allowlist."""
    async def capture(self, source: SourceDefinition) -> list[CapturedRecord]:
        raise NotImplementedError("Slack adapter requires approved bot-token configuration")


class LohiViewAdapter(SourceAdapter):
    """Reads migration-owned views/dossiers only; no natural-language or model-supplied SQL exists here."""
    async def capture(self, source: SourceDefinition) -> list[CapturedRecord]:
        if not source.view:
            raise ValueError("LoHi source is missing its approved view")
        raise NotImplementedError("LoHi view adapter requires the read-only dossier connection")


class StaticFileAdapter(SourceAdapter):
    """Explicitly listed UTF-8 files for interim, reviewable corpus seeding."""

    async def capture(self, source: SourceDefinition) -> list[CapturedRecord]:
        if not source.path:
            raise ValueError("static source is missing a path")
        path = Path(source.path)
        body = path.read_text(encoding="utf-8")
        stat = path.stat()
        return [CapturedRecord(
            native_id=str(path.resolve()), body=body, source_url=None,
            occurred_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC), metadata={"filename": path.name},
        )]
