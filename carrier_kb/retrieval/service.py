from __future__ import annotations

from dataclasses import dataclass

from carrier_kb.domain import Principal
from carrier_kb.retrieval.repository import Evidence, KnowledgeRepository


@dataclass(frozen=True)
class Answer:
    text: str
    evidence: tuple[Evidence, ...]


class AnswerService:
    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    async def answer(self, question: str, principal: Principal) -> Answer:
        evidence = await self.repository.search(question, principal.searchable_corpora)
        if not evidence:
            return Answer(
                text="I don't have an approved source that answers that yet. Please contact your LoHi recruiter.",
                evidence=(),
            )
        # LLM synthesis belongs here once the retrieval/evaluation contract is approved. Returning
        # evidence first makes the safety boundary testable and keeps this scaffold non-deceptive.
        return Answer(text=evidence[0].body, evidence=tuple(evidence))
