from datetime import UTC, datetime

import pytest

from carrier_kb.market.client import LohiMarketCatalogClient, LohiMarketOpportunityClient


def test_market_client_is_disabled_without_explicit_view():
    client = LohiMarketCatalogClient("postgresql://unused", "")
    assert client.configured is False


def test_market_client_rejects_unsafe_view_name():
    with pytest.raises(ValueError, match="invalid LoHi market catalog view"):
        LohiMarketCatalogClient("postgresql://unused", "catalog; DROP TABLE sources")


def test_opportunity_client_is_disabled_without_explicit_view():
    client = LohiMarketOpportunityClient("postgresql://unused", "")
    assert client.configured is False


def test_opportunity_client_rejects_unsafe_view_name():
    with pytest.raises(ValueError, match="invalid LoHi market opportunity view"):
        LohiMarketOpportunityClient("postgresql://unused", "view; DROP TABLE sources")


def test_market_projection_is_strict_and_aggregate_only():
    context = LohiMarketCatalogClient._to_context((
        "market-1", "Southern CA", "America/Los_Angeles", 120, 450,
        datetime.now(UTC),
        [{"facility_id": "facility-1", "name": "Example Facility", "city": "Example", "state": "CA", "completed_load_count_90d": 42}],
        [{"trailer_type": "dry_van", "recent_load_count": 85}],
        datetime.now(UTC),
    ))
    assert context.market_name == "Southern CA"
    assert context.facilities[0].completed_load_count_90d == 42
    assert context.equipment[0].trailer_type == "dry_van"
