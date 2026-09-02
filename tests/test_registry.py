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
