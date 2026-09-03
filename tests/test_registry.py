from pathlib import Path

import pytest

from carrier_kb.ingest.registry import load_registry


def test_example_registry_loads():
    registry = load_registry(Path("config/sources.example.yaml"))
    assert [item.id for item in registry] == [
        "carrier-guide", "carrier-ops-decisions", "onboarding-status-explanations"
    ]


def test_registry_rejects_unbounded_slack_source(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("sources:\n  - id: bad\n    kind: slack\n    visibility: carrier_internal\n    owner: a@b.com\n    refresh: '* * * * *'\n")
    with pytest.raises(ValueError, match="channel_ids"):
        load_registry(path)


@pytest.mark.asyncio
async def test_static_file_adapter_reads_only_explicit_path(tmp_path):
    from carrier_kb.ingest.adapters import StaticFileAdapter

    content = tmp_path / "notes.txt"
    content.write_text("approved onboarding note", encoding="utf-8")
    registry = tmp_path / "sources.yaml"
    registry.write_text(
        f"sources:\n  - id: notes\n    kind: static_file\n    visibility: carrier_internal\n    owner: ops\n    path: {content}\n    refresh: manual\n",
        encoding="utf-8",
    )
    source = load_registry(registry)[0]
    records = await StaticFileAdapter().capture(source)
    assert records[0].body == "approved onboarding note"


@pytest.mark.asyncio
async def test_front_adapter_filters_and_groups_messages(tmp_path):
    from carrier_kb.ingest.adapters import FrontCsvAdapter

    csv_path = tmp_path / "front.csv"
    csv_path.write_text(
        "Conversation ID,Message ID,Subject,Extract,Tags\n"
        "c1,m1,RMIS question,How do I complete insurance?,\n"
        "c1,m2,RMIS question,Follow up on the packet,\n"
        "c2,m3,Recruiting blast,Join our fleet today,\n"
        "c3,m4,Meta ads receipt,Payment summary for paid posting,\n",
        encoding="utf-8",
    )
    registry = tmp_path / "sources.yaml"
    registry.write_text(
        f"sources:\n  - id: front\n    kind: front_csv\n    visibility: carrier_internal\n    owner: ops\n    path: {csv_path}\n    refresh: manual\n",
        encoding="utf-8",
    )
    source = load_registry(registry)[0]
    records = await FrontCsvAdapter().capture(source)
    assert len(records) == 1
    assert records[0].native_id == "c1"
    assert "insurance" in records[0].body
    assert "verification" in records[0].body
