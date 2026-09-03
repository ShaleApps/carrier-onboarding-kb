from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from carrier_kb.ingest.adapters import FrontCsvAdapter, StaticFileAdapter
from carrier_kb.ingest.ome import OmeTranscriptAdapter
from carrier_kb.ingest.registry import load_registry
from carrier_kb.ingest.writer import PostgresIngestWriter
from carrier_kb.settings import Settings


async def ingest(registry_path: Path, source_id: str | None = None) -> int:
    settings = Settings()
    if not settings.kb_dsn:
        raise RuntimeError("KB_DSN must be configured before ingesting")
    sources = load_registry(registry_path)
    if source_id:
        sources = [source for source in sources if source.id == source_id]
        if not sources:
            raise ValueError(f"source not found in registry: {source_id}")
    writer = PostgresIngestWriter(settings.kb_dsn)
    total = 0
    for source in sources:
        if source.kind not in {"static_file", "front_csv", "ome_transcripts"}:
            raise RuntimeError(f"adapter not enabled for source kind: {source.kind}")
        if source.kind == "front_csv":
            adapter = FrontCsvAdapter()
        elif source.kind == "ome_transcripts":
            adapter = OmeTranscriptAdapter(settings.ome_analytics_dsn)
        else:
            adapter = StaticFileAdapter()
        records = await adapter.capture(source)
        total += await writer.write(source, records)
        print(f"ingested {len(records)} record(s): {source.id}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest explicitly approved Carrier KB sources")
    parser.add_argument("--registry", type=Path, default=Path("config/sources.yaml"))
    parser.add_argument("--source", dest="source_id", help="ingest one registry source only")
    args = parser.parse_args()
    count = asyncio.run(ingest(args.registry, args.source_id))
    print(f"ingested {count} record(s) total")


if __name__ == "__main__":
    main()
