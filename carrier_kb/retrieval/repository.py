from __future__ import annotations

from dataclasses import dataclass

import psycopg

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


class PostgresKnowledgeRepository(KnowledgeRepository):
    """Read-only full-text retrieval over approved, corpus-scoped documents."""

    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("KB DSN is required")
        self.dsn = dsn

    async def search(self, question: str, corpora: tuple[Corpus, ...], limit: int = 8) -> list[Evidence]:
        if not corpora:
            return []
        limit = max(1, min(limit, 20))
        async with await psycopg.AsyncConnection.connect(self.dsn) as connection, connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT d.id::text, d.body, s.registry_id, s.native_id, s.title, s.source_url
                    FROM documents d
                    JOIN document_sources ds ON ds.document_id = d.id
                    JOIN sources s ON s.id = ds.source_id
                    WHERE d.corpus = ANY(%s::kb_corpus[])
                      AND d.valid_from <= now()
                      AND (d.valid_until IS NULL OR d.valid_until > now())
                      AND d.body_tsv @@ replace(plainto_tsquery('english', %s)::text, ' & ', ' | ')::tsquery
                    ORDER BY ts_rank_cd(
                               d.body_tsv,
                               replace(plainto_tsquery('english', %s)::text, ' & ', ' | ')::tsquery
                             ) DESC,
                             d.created_at DESC
                    LIMIT %s
                    """,
                    ([corpus.value for corpus in corpora], question, question, limit),
                )
                rows = await cursor.fetchall()
        return [
            Evidence(
                document_id=row[0],
                body=row[1],
                citations=(Citation(source_id=f"{row[2]}:{row[3]}", title=row[4], url=row[5]),),
            )
            for row in rows
        ]
