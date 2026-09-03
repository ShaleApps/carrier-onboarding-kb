from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel, Field

from carrier_kb.auth.carrier_hub import CarrierHubAuthorizer
from carrier_kb.carrier_hub.client import HttpCarrierHubContextClient
from carrier_kb.domain import Principal
from carrier_kb.retrieval.repository import KnowledgeRepository, PostgresKnowledgeRepository
from carrier_kb.retrieval.service import AnswerService
from carrier_kb.settings import Settings


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=200)


class UnconfiguredRepository(KnowledgeRepository):
    async def search(self, question, corpora, limit=8):
        return []


def create_app() -> FastAPI:
    settings = Settings()
    authorizer = CarrierHubAuthorizer(settings)
    repository = PostgresKnowledgeRepository(settings.kb_dsn) if settings.kb_dsn else UnconfiguredRepository()
    answers = AnswerService(
        repository,
        carrier_hub=HttpCarrierHubContextClient(settings.carrier_hub_api_base_url),
    )
    app = FastAPI(title="Carrier Onboarding KB", version="0.1.0")

    async def principal(request: Request) -> Principal:
        return await authorizer.principal(request)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.post("/v1/answer")
    async def answer(payload: AskRequest, caller: Annotated[Principal, Depends(principal)]):
        result = await answers.answer(payload.question, caller)
        return {
            "answer": result.text,
            "answer_type": result.answer_type,
            "confidence": result.confidence,
            "next_action": result.next_action,
            "citations": [
                {"document_id": item.document_id, "sources": [citation.__dict__ for citation in item.citations]}
                for item in result.evidence
            ],
            "audience": caller.audience,
        }

    return app
