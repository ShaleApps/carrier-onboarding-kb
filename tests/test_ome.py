import pytest

from carrier_kb.ingest.ome import OmeTranscriptAdapter


def test_ome_adapter_requires_explicit_dsn():
    with pytest.raises(ValueError, match="OME_ANALYTICS_DSN"):
        OmeTranscriptAdapter("")


def test_ome_adapter_relevance_filter_is_conservative():
    assert OmeTranscriptAdapter._is_relevant("Carrier needs an RMIS packet")
    assert not OmeTranscriptAdapter._is_relevant("Unrelated product discussion")
