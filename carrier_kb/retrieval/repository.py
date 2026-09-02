from __future__ import annotations

from dataclasses import dataclass

from carrier_kb.domain import Corpus


@dataclass(frozen=True)
class Citation:
    source_id: str
    title: str
    url: str | None


@dataclass(frozen=True)
class Evidence:
    document_id: str
    body: str
    citations: tuple[Citation, ...]


class KnowledgeRepository:
    """Persistence seam for hybrid retrieval.

    The SQL implementation will bind the corpora array supplied by the Principal. It must
    never treat corpus membership as an optional model-provided filter.
    """
    async def search(self, question: str, corpora: tuple[Corpus, ...], limit: int = 8) -> list[Evidence]:
        raise NotImplementedError
