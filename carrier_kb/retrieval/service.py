from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI, OpenAIError

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
    application_status: dict | None = None


class AnswerService:
    def __init__(self, repository: KnowledgeRepository, carrier_hub: CarrierHubContextClient | None = None,
                 *, openai_api_key: str = "", answer_model: str = "gpt-5-mini", synthesis_enabled: bool = False):
        self.repository = repository
        self.carrier_hub = carrier_hub
        self.synthesis_enabled = synthesis_enabled and bool(openai_api_key)
        self.answer_model = answer_model
        self.openai = AsyncOpenAI(api_key=openai_api_key) if self.synthesis_enabled else None

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
                application_status=self._status_card(context),
            )
        text = evidence[0].body
        lowered = text.lower()
        conditional = any(term in lowered for term in ("context-dependent", "conflicting", "program-specific"))
        if self.openai and not conditional:
            text = await self._synthesize(question, evidence)
        return Answer(
            text=text,
            evidence=tuple(evidence),
            answer_type="conditional_policy" if conditional else "policy",
            confidence="conditional" if conditional else "supported",
            next_action=("Confirm the applicable program or region with your LoHi recruiter."
                          if conditional else None),
        )

    async def _synthesize(self, question: str, evidence: list[Evidence]) -> str:
        source_text = "\n\n".join(item.body for item in evidence[:8])
        try:
            response = await self.openai.chat.completions.create(
                model=self.answer_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": (
                        "Answer only from the supplied approved evidence. Be concise. "
                        "Do not invent policy, dates, amounts, or requirements. If the "
                        "evidence is insufficient, say so and advise contacting a recruiter."
                    )},
                    {"role": "user", "content": f"Question: {question}\n\nApproved evidence:\n{source_text}"},
                ],
            )
            return response.choices[0].message.content or evidence[0].body
        except (OpenAIError, RuntimeError, TimeoutError):
            return evidence[0].body

    @staticmethod
    def _context_body(context) -> str:
        requirements = ", ".join(f"{item.label}: {item.state.value}" for item in context.requirements)
        return (
            f"Live application status: {context.status} ({context.stage}). "
            f"{context.status_explanation or ''} "
            f"Requirements: {requirements or 'none reported'}."
        ).strip()

    @staticmethod
    def _status_card(context) -> dict:
        requirements = [item.model_dump(mode="json") for item in context.requirements]
        blocking = [item for item in requirements if item["blocking"] and item["state"] != "satisfied"]
        completed = [item for item in requirements if item["state"] in {"satisfied", "not_applicable"}]
        return {
            "stage": context.stage,
            "status": context.status,
            "explanation": context.status_explanation,
            "blocking_requirements": blocking,
            "completed_requirements": completed,
            "next_action": context.next_action.model_dump(mode="json") if context.next_action else None,
            "updated_at": context.context_updated_at.isoformat(),
        }
