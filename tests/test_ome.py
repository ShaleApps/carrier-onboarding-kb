import pytest

from carrier_kb.ingest.ome import OmeTranscriptAdapter


def test_ome_adapter_requires_explicit_dsn():
    with pytest.raises(ValueError, match="OME_ANALYTICS_DSN"):
        OmeTranscriptAdapter("")
