from datetime import UTC, datetime

import pytest

from carrier_kb.carrier_hub.models import ApplicationContext
from carrier_kb.domain import Audience, Principal
from carrier_kb.retrieval.repository import Citation, Evidence, KnowledgeRepository
from carrier_kb.retrieval.service import AnswerService


class FixedRepository(KnowledgeRepository):
    def __init__(self, evidence):
        self.evidence = evidence

    async def search(self, question, corpora, limit=8):
        return list(self.evidence)


class EmptyRepository(KnowledgeRepository):
    async def search(self, question, corpora, limit=8):
        return []


class LiveCarrierHub:
    async def get_application_context(self, application_id, bearer_token, audience):
        return ApplicationContext(
            application_id=application_id,
            audience=audience,
            brokerage_slug="bainbridge",
            stage="verification",
            status="in_progress",
            requirements=(),
            context_updated_at=datetime.now(UTC),
        )


class FakeCompletions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error

    async def create(self, **kwargs):
        if self.error:
            raise self.error
        class Message:
            pass
        class Choice:
            pass
        message, choice = Message(), Choice()
        message.content = self.content
        choice.message = message
        class Response:
            pass
        response = Response()
        response.choices = [choice]
        return response


class FakeOpenAI:
    def __init__(self, content=None, error=None):
        self.chat = type("Chat", (), {"completions": FakeCompletions(content, error)})()


@pytest.mark.asyncio
async def test_unsupported_answer_is_explicit_handoff():
    result = await AnswerService(EmptyRepository()).answer(
        "Where do I submit this?", Principal("carrier", Audience.CARRIER)
    )
    assert result.answer_type == "handoff"
    assert result.confidence == "unsupported"
    assert result.next_action


@pytest.mark.asyncio
async def test_conditional_policy_is_not_presented_as_definitive():
    evidence = Evidence("policy", "This is program-specific and context-dependent.", (Citation("front", "Policy", None),))
    result = await AnswerService(FixedRepository([evidence])).answer(
        "What is required?", Principal("carrier", Audience.CARRIER)
    )
    assert result.answer_type == "conditional_policy"
    assert result.confidence == "conditional"
    assert result.next_action


@pytest.mark.asyncio
async def test_live_status_is_structured():
    result = await AnswerService(EmptyRepository(), LiveCarrierHub()).answer(
        "What is my status?",
        Principal("carrier", Audience.CARRIER, application_id="app-1", access_token="cap"),
    )
    assert result.answer_type == "application_status"
    assert result.confidence == "live"
    assert "in_progress" in result.text
    assert result.application_status["stage"] == "verification"
    assert result.application_status["blocking_requirements"] == []
    assert result.application_status["completed_requirements"] == []


@pytest.mark.asyncio
async def test_synthesis_uses_model_text_when_enabled():
    evidence = Evidence("policy", "Approved policy text", (Citation("front", "Policy", None),))
    service = AnswerService(FixedRepository([evidence]), synthesis_enabled=False)
    service.openai = FakeOpenAI("Concise grounded answer")
    result = await service.answer("What is the policy?", Principal("carrier", Audience.CARRIER))
    assert result.text == "Concise grounded answer"


@pytest.mark.asyncio
async def test_synthesis_empty_response_falls_back_to_evidence():
    evidence = Evidence("policy", "Approved policy text", (Citation("front", "Policy", None),))
    service = AnswerService(FixedRepository([evidence]), synthesis_enabled=False)
    service.openai = FakeOpenAI(None)
    result = await service.answer("What is the policy?", Principal("carrier", Audience.CARRIER))
    assert result.text == "Approved policy text"


@pytest.mark.asyncio
async def test_synthesis_failure_falls_back_to_evidence():
    evidence = Evidence("policy", "Approved policy text", (Citation("front", "Policy", None),))
    service = AnswerService(FixedRepository([evidence]), synthesis_enabled=False)
    service.openai = FakeOpenAI(error=RuntimeError("provider unavailable"))
    result = await service.answer("What is the policy?", Principal("carrier", Audience.CARRIER))
    assert result.text == "Approved policy text"
