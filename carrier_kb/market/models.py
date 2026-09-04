from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketFacility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=300)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    completed_load_count_90d: int = Field(ge=10)


class MarketEquipment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trailer_type: str = Field(min_length=1, max_length=100)
    recent_load_count: int = Field(ge=10)


class MarketContext(BaseModel):
    """Carrier-safe aggregate market projection, never raw load data."""

    model_config = ConfigDict(extra="forbid")

    market_id: str = Field(min_length=1, max_length=100)
    market_name: str = Field(min_length=1, max_length=200)
    timezone: str | None = Field(default=None, max_length=100)
    recent_load_count: int = Field(ge=0)
    completed_load_count_90d: int = Field(ge=0)
    last_completed_load_at: datetime | None = None
    facilities: tuple[MarketFacility, ...] = ()
    equipment: tuple[MarketEquipment, ...] = ()
    refreshed_at: datetime
