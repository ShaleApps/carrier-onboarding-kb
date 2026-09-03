import pytest

from carrier_kb.ingest.cli import ingest


@pytest.mark.asyncio
async def test_ingest_fails_closed_without_dsn(tmp_path, monkeypatch):
    monkeypatch.delenv("KB_DSN", raising=False)
    registry = tmp_path / "sources.yaml"
    registry.write_text("sources: []", encoding="utf-8")
    with pytest.raises(RuntimeError, match="KB_DSN"):
        await ingest(registry)
