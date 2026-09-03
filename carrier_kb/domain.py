from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Corpus(StrEnum):
    PUBLIC = "carrier_public"
    INTERNAL = "carrier_internal"


class Audience(StrEnum):
    CARRIER = "carrier"
    INTERNAL = "internal"


@dataclass(frozen=True)
class Principal:
    subject: str
    audience: Audience
    application_id: str | None = None
    brokerage_id: str | None = None
    access_token: str | None = None

    @property
    def searchable_corpora(self) -> tuple[Corpus, ...]:
        if self.audience is Audience.INTERNAL:
            return (Corpus.PUBLIC, Corpus.INTERNAL)
        return (Corpus.PUBLIC,)
