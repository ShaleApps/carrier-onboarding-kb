from __future__ import annotations

import logging
import time
from uuid import uuid4

import httpx
import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from carrier_kb.auth.carrier_hub import CarrierHubAuthorizer
from carrier_kb.carrier_hub.client import HttpCarrierHubContextClient
from carrier_kb.domain import Principal
from carrier_kb.retrieval.repository import KnowledgeRepository, PostgresKnowledgeRepository
from carrier_kb.retrieval.service import AnswerService
from carrier_kb.settings import Settings

logger = logging.getLogger("carrier_kb.api")


class AskRequest(BaseModel):
    # Application authority comes only from the signed capability token, never the body.
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=200)


class UnconfiguredRepository(KnowledgeRepository):
    async def search(self, question, corpora, limit=8):
        return []


def create_app() -> FastAPI:
    settings = Settings()
    authorizer = CarrierHubAuthorizer(settings)
    repository = PostgresKnowledgeRepository(settings.kb_dsn, settings.kb_schema) if settings.kb_dsn else UnconfiguredRepository()
    answers = AnswerService(
        repository,
        carrier_hub=HttpCarrierHubContextClient(settings.carrier_hub_api_base_url),
        openai_api_key=settings.openai_api_key,
        answer_model=settings.answer_model,
        synthesis_enabled=settings.answer_synthesis_enabled,
    )
    app = FastAPI(title="Carrier Onboarding KB", version="0.1.0")

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["x-request-id"] = request_id
        logger.info("request_complete", extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
        })
        return response

    async def principal(request: Request) -> Principal:
        return await authorizer.principal(request)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        configured = bool(settings.kb_dsn and settings.carrier_hub_api_base_url)
        database_ready = False
        if configured:
            try:
                async with (await psycopg.AsyncConnection.connect(settings.kb_dsn, connect_timeout=2)) as connection, connection.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    database_ready = (await cursor.fetchone()) == (1,)
            except (psycopg.Error, OSError):
                database_ready = False
        ready = configured and database_ready
        body = {"status": "ready" if ready else "not_ready", "database": "ok" if database_ready else "unavailable"}
        return JSONResponse(status_code=200 if ready else 503, content=body)

    @app.post("/v1/answer")
    async def answer(request: Request, payload: AskRequest, caller: Principal = Depends(principal)):  # noqa: B008
        try:
            result = await answers.answer(payload.question, caller)
        except (psycopg.Error, httpx.HTTPError, TimeoutError):
            logger.exception("answer_dependency_failure", extra={"request_id": request.state.request_id})
            return JSONResponse(
                status_code=503,
                content={
                    "error": "service temporarily unavailable",
                    "message": "Please retry shortly or contact your LoHi recruiter.",
                    "request_id": request.state.request_id,
                },
            )
        logger.info("answer_complete", extra={
            "request_id": request.state.request_id,
            "answer_type": result.answer_type,
            "confidence": result.confidence,
            "evidence_count": len(result.evidence),
        })
        return {
            "answer": result.text,
            "answer_type": result.answer_type,
            "confidence": result.confidence,
            "next_action": result.next_action,
            "application_status": result.application_status,
            "citations": [
                {"document_id": item.document_id, "sources": [citation.__dict__ for citation in item.citations]}
                for item in result.evidence
            ],
            "audience": caller.audience,
        }

    return app
