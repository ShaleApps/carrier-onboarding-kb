from __future__ import annotations

import re
from typing import Any

import psycopg
from psycopg import sql

from carrier_kb.market.models import MarketContext


class LohiMarketCatalogClient:
    """Reads one DBA-approved aggregate view, never caller-provided SQL.

    The configured view must implement the projection described in
    ``docs/market-catalog-data-contract.md``. Leaving it unset disables this
    integration until the market-owner disclosure review is complete.
    """

    _NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

    def __init__(self, dsn: str, view: str):
        self.dsn = dsn
        self.view = view
        if view and not self._NAME.fullmatch(view):
            raise ValueError("invalid LoHi market catalog view")

    @property
    def configured(self) -> bool:
        return bool(self.dsn and self.view)

    async def get_market(self, market_name: str) -> MarketContext | None:
        """Return one exact case-insensitive market match from the approved view."""
        if not self.configured:
            return None
        normalized = " ".join(market_name.split())
        if not normalized or len(normalized) > 200:
            raise ValueError("invalid market name")
        query = sql.SQL("""
            SELECT market_id::text, market_name, timezone, recent_load_count,
                   completed_load_count_90d, last_completed_load_at,
                   facilities, equipment, refreshed_at
            FROM {view}
            WHERE lower(market_name) = lower(%s)
            LIMIT 2
        """).format(view=sql.Identifier(self.view))
        async with await psycopg.AsyncConnection.connect(self.dsn) as connection, connection.cursor() as cursor:
            await cursor.execute("SET TRANSACTION READ ONLY")
            await cursor.execute(query, (normalized,))
            rows = await cursor.fetchall()
        if len(rows) > 1:
            raise ValueError("market catalog has ambiguous market names")
        if not rows:
            return None
        return self._to_context(rows[0])

    @staticmethod
    def _to_context(row: tuple[Any, ...]) -> MarketContext:
        return MarketContext(
            market_id=str(row[0]),
            market_name=row[1],
            timezone=row[2],
            recent_load_count=row[3],
            completed_load_count_90d=row[4],
            last_completed_load_at=row[5],
            facilities=tuple(row[6] or ()),
            equipment=tuple(row[7] or ()),
            refreshed_at=row[8],
        )
