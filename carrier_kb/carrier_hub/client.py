from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from carrier_kb.carrier_hub.models import ApplicationContext, ContextAudience


class CarrierHubContextClient(Protocol):
    async def get_application_context(
        self, application_id: str, bearer_token: str, audience: ContextAudience
    ) -> ApplicationContext:
        """Fetch a Carrier Hub-owned, audience-filtered read projection."""


class HttpCarrierHubContextClient:
    """Read-only client for Carrier Hub's existing application status endpoint.

    The endpoint returns a broad application object. This adapter intentionally
    whitelists and translates only the fields needed by the KB.
    """

    def __init__(
        self, base_url: str, timeout: float = 5.0, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    @staticmethod
    def _validate_application_id(application_id: str) -> None:
        if not application_id or "/" in application_id or "?" in application_id:
            raise ValueError("invalid application_id")

    async def get_application_context(
        self, application_id: str, bearer_token: str, audience: ContextAudience
    ) -> ApplicationContext:
        self._validate_application_id(application_id)
        if not bearer_token:
            raise ValueError("bearer_token is required")

        path_id = quote(application_id, safe="-_.~")
        url = f"{self.base_url}/api/v1/application/{path_id}/status"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        # GetApplicationStatus uses the conventional {item: ...} envelope.
        item = payload.get("item", payload) if isinstance(payload, dict) else payload
        context = self._sanitize_status(item, application_id, audience)
        if context.application_id != application_id:
            raise ValueError("Carrier Hub returned an unexpected application")
        return context

    @staticmethod
    def _sanitize_status(item: Any, application_id: str, audience: ContextAudience) -> ApplicationContext:
        if not isinstance(item, dict):
            raise TypeError("Carrier Hub returned an invalid application status")
        application_id_from_api = item.get("id")
        updated_at = item.get("updatedAt") or item.get("updated_at")
        brokerage = item.get("brokerage") or {}
        brokerage_slug = brokerage.get("slug") if isinstance(brokerage, dict) else None
        if not application_id_from_api or not brokerage_slug or not updated_at:
            raise ValueError("Carrier Hub returned incomplete application status")
        status = str(item.get("status") or "unknown")
        if status == "onboarding_completed":
            stage, explanation, action = "completed", "Onboarding is complete.", None
        elif status == "rejected":
            stage, explanation, action = "rejected", "The application requires internal review.", None
        elif status == "error":
            stage, explanation, action = "error", "The application has an internal processing error.", None
        else:
            stage, explanation, action = "verification", "Onboarding requirements are still in progress.", None
        context_updated_at = datetime.fromisoformat(str(updated_at))
        return ApplicationContext(
            application_id=str(application_id_from_api),
            audience=audience,
            brokerage_slug=str(brokerage_slug),
            stage=stage,
            status=status,
            status_explanation=explanation,
            next_action=action,
            context_updated_at=context_updated_at.astimezone(UTC),
        )
