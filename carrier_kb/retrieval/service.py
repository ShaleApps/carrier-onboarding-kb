from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from openai import AsyncOpenAI, OpenAIError

from carrier_kb.carrier_hub.client import CarrierHubContextClient
from carrier_kb.carrier_hub.models import ContextAudience
from carrier_kb.domain import Principal
from carrier_kb.market.models import MarketContext, MarketOpportunityContext
from carrier_kb.retrieval.repository import Citation, Evidence, KnowledgeRepository


@dataclass(frozen=True)
class Answer:
    text: str
    evidence: tuple[Evidence, ...]
    answer_type: str = "policy"
    confidence: str = "supported"
    next_action: str | None = None
    application_status: dict | None = None


class MarketCatalogClient(Protocol):
    configured: bool

    async def get_market(self, market_name: str) -> MarketContext | None: ...


class MarketOpportunityClient(Protocol):
    configured: bool

    async def get_market(self, market_name: str) -> MarketOpportunityContext | None: ...


class QuestionRoute(StrEnum):
    POLICY = "policy"
    APPLICATION_STATUS = "application_status"
    MARKET_CATALOG = "market_catalog"
    MARKET_OPPORTUNITY = "market_opportunity"
    EARNINGS = "earnings"


class AnswerService:
    def __init__(self, repository: KnowledgeRepository, carrier_hub: CarrierHubContextClient | None = None,
                 market_catalog: MarketCatalogClient | None = None,
                 market_opportunity: MarketOpportunityClient | None = None,
                 *, openai_api_key: str = "", answer_model: str = "gpt-5-mini", synthesis_enabled: bool = False):
        self.repository = repository
        self.carrier_hub = carrier_hub
        self.market_catalog = market_catalog
        self.market_opportunity = market_opportunity
        self.synthesis_enabled = synthesis_enabled and bool(openai_api_key)
        self.answer_model = answer_model
        self.openai = AsyncOpenAI(api_key=openai_api_key) if self.synthesis_enabled else None

    async def answer(self, question: str, principal: Principal, market_name: str | None = None) -> Answer:
        route = self._route(question)
        if route is QuestionRoute.APPLICATION_STATUS and self.carrier_hub and principal.application_id:
            context = await self.carrier_hub.get_application_context(
                principal.application_id,
                principal.access_token or "",
                ContextAudience.INTERNAL if principal.audience.value == "internal" else ContextAudience.PUBLIC,
            )
            evidence = (Evidence(
                document_id=f"carrier-hub:{context.application_id}",
                body=self._context_body(context),
                citations=(Citation(source_id="carrier_hub", title="Live Carrier Hub application status", url=None),),
            ),)
            action = context.next_action.description if context.next_action else None
            return Answer(
                text=self._context_body(context), evidence=evidence, answer_type="application_status",
                confidence="live", next_action=action, application_status=self._status_card(context),
            )
        if route is QuestionRoute.MARKET_CATALOG and market_name:
            return await self._market_catalog_answer(market_name)
        if route is QuestionRoute.MARKET_OPPORTUNITY and market_name:
            return await self._market_opportunity_answer(market_name)
        if route is QuestionRoute.EARNINGS:
            qualifier = f" for {market_name}" if market_name else ""
            return Answer(
                text=(f"I don't have an approved current earnings metric{qualifier} yet. "
                      "Please contact your LoHi recruiter for confirmed current earnings guidance."),
                evidence=(), answer_type="handoff", confidence="unsupported",
                next_action="Contact your LoHi recruiter for confirmed current earnings guidance.",
            )

        evidence = await self.repository.search(question, principal.searchable_corpora)
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

    @staticmethod
    def _route(question: str) -> QuestionRoute:
        lowered = question.lower()
        if any(term in lowered for term in (
            "application status", "my status", "what is pending", "what's pending",
            "where am i", "where do i stand", "my next step",
        )):
            return QuestionRoute.APPLICATION_STATUS
        if any(term in lowered for term in (
            "earnings", "average driver", "typical driver", "per shift", "per load",
            "how much can i make", "how much do you pay", "what is the rate",
        )):
            return QuestionRoute.EARNINGS
        if any(term in lowered for term in (
            "available loads", "open loads", "load availability", "market active",
            "market activity", "currently active",
        )):
            return QuestionRoute.MARKET_OPPORTUNITY
        if any(term in lowered for term in (
            "facility", "facilities", "equipment", "trailer", "market",
        )):
            return QuestionRoute.MARKET_CATALOG
        return QuestionRoute.POLICY

    async def _market_catalog_answer(self, market_name: str) -> Answer:
        if not self.market_catalog or not self.market_catalog.configured:
            return self._market_handoff(market_name)
        context = await self.market_catalog.get_market(market_name)
        if not context:
            return self._market_handoff(market_name)
        facilities = ", ".join(f"{item.name} ({item.city}, {item.state})" for item in context.facilities)
        equipment = ", ".join(item.trailer_type.replace("_", " ") for item in context.equipment)
        body = f"{context.market_name} market information."
        if facilities:
            body += f" Common facilities: {facilities}."
        if equipment:
            body += f" Recent compatible equipment: {equipment}."
        body += " This is historical market guidance, not a guarantee of load availability."
        return Answer(
            text=body,
            evidence=(Evidence(
                document_id=f"lohi-market-catalog:{context.market_id}", body=body,
                citations=(Citation("lohi_market_catalog", "Live LoHi market catalog", None),),
            ),),
            answer_type="market_catalog", confidence="live",
        )

    async def _market_opportunity_answer(self, market_name: str) -> Answer:
        if not self.market_opportunity or not self.market_opportunity.configured:
            return self._market_handoff(market_name)
        context = await self.market_opportunity.get_market(market_name)
        if not context:
            return self._market_handoff(market_name)
        equipment = ", ".join(item.trailer_type.replace("_", " ") for item in context.equipment)
        body = f"Current market activity for {context.market_name}: {context.availability}."
        if equipment:
            body += f" Recent compatible equipment includes {equipment}."
        body += " This is not a booking guarantee or a carrier-specific rate quote."
        return Answer(
            text=body,
            evidence=(Evidence(
                document_id=f"lohi-market-opportunity:{context.market_id}", body=body,
                citations=(Citation("lohi_market_opportunity", "Live LoHi market opportunity", None),),
            ),),
            answer_type="market_opportunity", confidence="live",
        )

    @staticmethod
    def _market_handoff(market_name: str) -> Answer:
        return Answer(
            text=(f"I don't have current approved market data for {market_name} yet. "
                  "Please contact your LoHi recruiter for current market guidance."),
            evidence=(), answer_type="handoff", confidence="unsupported",
            next_action="Contact your LoHi recruiter for current market guidance.",
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
