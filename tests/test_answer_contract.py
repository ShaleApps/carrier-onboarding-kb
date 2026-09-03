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
