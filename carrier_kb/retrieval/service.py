from __future__ import annotations

from dataclasses import dataclass

from carrier_kb.carrier_hub.client import CarrierHubContextClient
from carrier_kb.carrier_hub.models import ContextAudience
from carrier_kb.domain import Principal
from carrier_kb.retrieval.repository import Citation, Evidence, KnowledgeRepository


@dataclass(frozen=True)
class Answer:
    text: str
    evidence: tuple[Evidence, ...]
    answer_type: str = "policy"
    confidence: str = "supported"
    next_action: str | None = None


class AnswerService:
    def __init__(self, repository: KnowledgeRepository, carrier_hub: CarrierHubContextClient | None = None):
        self.repository = repository
        self.carrier_hub = carrier_hub

    async def answer(self, question: str, principal: Principal) -> Answer:
        evidence = await self.repository.search(question, principal.searchable_corpora)
        if self.carrier_hub and principal.application_id:
            context = await self.carrier_hub.get_application_context(
                principal.application_id,
                principal.access_token or "",
                ContextAudience.INTERNAL if principal.audience.value == "internal" else ContextAudience.PUBLIC,
            )
            evidence.insert(0, Evidence(
                document_id=f"carrier-hub:{context.application_id}",
                body=self._context_body(context),
                citations=(Citation(source_id="carrier_hub", title="Live Carrier Hub application status", url=None),),
            ))
        if not evidence:
            return Answer(
                text="I don't have an approved source that answers that yet. Please contact your LoHi recruiter.",
                evidence=(),
                answer_type="handoff",
                confidence="unsupported",
                next_action="Contact your LoHi recruiter for a confirmed answer.",
            )
        # LLM synthesis belongs here once the retrieval/evaluation contract is approved. Returning
        # evidence first makes the safety boundary testable and keeps this scaffold non-deceptive.
        if principal.application_id and evidence[0].document_id.startswith("carrier-hub:"):
            action = context.next_action.description if context.next_action else None
            return Answer(
                text=self._context_body(context),
                evidence=tuple(evidence),
                answer_type="application_status",
                confidence="live",
                next_action=action,
            )
        return Answer(text=evidence[0].body, evidence=tuple(evidence))

    @staticmethod
    def _context_body(context) -> str:
        requirements = ", ".join(f"{item.label}: {item.state.value}" for item in context.requirements)
        return (
            f"Live application status: {context.status} ({context.stage}). "
            f"{context.status_explanation or ''} "
            f"Requirements: {requirements or 'none reported'}."
        ).strip()
