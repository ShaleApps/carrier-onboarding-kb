from __future__ import annotations

from typing import Protocol
from urllib.parse import quote

import httpx

from carrier_kb.carrier_hub.models import ApplicationContext, ContextAudience


class CarrierHubContextClient(Protocol):
    async def get_application_context(
        self, application_id: str, bearer_token: str, audience: ContextAudience
    ) -> ApplicationContext:
        """Fetch a Carrier Hub-owned, audience-filtered read projection."""


class HttpCarrierHubContextClient:
    """Read-only client for the future Carrier Hub KB context endpoint.

    This deliberately calls one narrow GET projection rather than the broad
    application endpoint. Carrier Hub must authenticate the token, verify the
    application scope, and omit unauthorized fields before returning JSON.
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
        url = f"{self.base_url}/api/v1/kb-context/applications/{path_id}"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "X-KB-Audience": audience.value,
        }
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        # Accept either the direct projection or the conventional {item: ...}
        # envelope used by Carrier Hub's existing gRPC-gateway endpoints.
        item = payload.get("item", payload) if isinstance(payload, dict) else payload
        context = ApplicationContext.model_validate(item)
        if context.audience is not audience:
            raise ValueError("Carrier Hub returned an unexpected audience projection")
        if context.application_id != application_id:
            raise ValueError("Carrier Hub returned an unexpected application")
        return context
