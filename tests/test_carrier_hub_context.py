from datetime import UTC, datetime

import httpx
import pytest

from carrier_kb.carrier_hub.client import HttpCarrierHubContextClient
from carrier_kb.carrier_hub.models import (
    ActionActor,
    ApplicationContext,
    ContextAudience,
    NextAction,
    Requirement,
    RequirementState,
)


def test_public_context_is_typed_and_does_not_accept_unknown_fields():
    now = datetime.now(UTC)
    context = ApplicationContext(
        application_id="app-123",
        audience=ContextAudience.PUBLIC,
        brokerage_slug="bainbridge",
        carrier_name="Example Transport",
        stage="verification",
        status="pending",
        next_action=NextAction(
            key="complete_rmis",
            title="Complete your RMIS registration",
            description="Open the registration link and finish the remaining steps.",
            actor=ActionActor.CARRIER,
            blocking=True,
            generated_at=now,
        ),
        requirements=(
            Requirement(
                key="rmis",
                label="RMIS registration",
                state=RequirementState.INVITED,
                blocking=True,
            ),
        ),
        context_updated_at=now,
    )
    assert context.next_action.actor is ActionActor.CARRIER
    with pytest.raises(ValueError):
        ApplicationContext(**context.model_dump(), internal_notes="must not cross boundary")


@pytest.mark.asyncio
async def test_client_is_get_only_and_validates_projection():
    now = datetime.now(UTC).isoformat()
    payload = {
        "item": {
            "id": "app-123",
            "status": "pending",
            "brokerage": {"slug": "bainbridge"},
            "updatedAt": now,
            "safelandRequired": True,
            "safelandCompletedAt": None,
            "rmisVerification": {"status": "invited", "updatedAt": now},
        }
    }
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = HttpCarrierHubContextClient("https://carrier-onboarding.example", transport=transport)
    context = await client.get_application_context("app-123", "token", ContextAudience.INTERNAL)

    assert context.application_id == "app-123"
    assert context.requirements[0].state is RequirementState.REQUIRED
    assert context.rmis is not None and context.rmis.action_required
    assert requests[0].method == "GET"
    assert requests[0].headers["authorization"] == "Bearer token"


def test_client_rejects_path_injection():
    client = HttpCarrierHubContextClient("https://carrier-onboarding.example")
    with pytest.raises(ValueError):
        client._validate_application_id("bad/id")
