from datetime import UTC, datetime

import pytest

from carrier_kb.carrier_hub.models import ApplicationContext
from carrier_kb.domain import Audience, Principal
from carrier_kb.retrieval.repository import Citation, Evidence, KnowledgeRepository
from carrier_kb.retrieval.service import AnswerService


class Repository(KnowledgeRepository):
    async def search(self, question, corpora, limit=8):
        return [Evidence("policy-1", "Approved policy", (Citation("drive-1", "Policy", None),))]


class CarrierHub:
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
async def test_live_context_is_first_class_evidence():
    service = AnswerService(Repository(), CarrierHub())
    result = await service.answer(
        "What is the application status?",
        Principal("user-1", Audience.INTERNAL, application_id="app-1", access_token="token"),
    )
    assert result.evidence[0].document_id == "carrier-hub:app-1"
    assert result.evidence[0].citations[0].source_id == "carrier_hub"
    assert result.evidence[1].document_id == "policy-1"


@pytest.mark.asyncio
async def test_without_application_id_only_policy_evidence_is_used():
    service = AnswerService(Repository(), CarrierHub())
    result = await service.answer("What is the policy?", Principal("user-1", Audience.INTERNAL))
    assert [item.document_id for item in result.evidence] == ["policy-1"]
