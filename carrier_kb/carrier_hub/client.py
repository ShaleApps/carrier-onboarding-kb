from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from carrier_kb.carrier_hub.models import (
    ApplicationContext,
    ContextAudience,
    Requirement,
    RequirementState,
    VerificationSummary,
)


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

    @classmethod
    def _sanitize_status(cls, item: Any, application_id: str, audience: ContextAudience) -> ApplicationContext:
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
            stage, explanation = "completed", "Onboarding is complete."
        elif status == "rejected":
            stage, explanation = "rejected", "The application requires internal review."
        elif status == "error":
            stage, explanation = "error", "The application has an internal processing error."
        else:
            stage, explanation = "verification", "Onboarding requirements are still in progress."
        context_updated_at = datetime.fromisoformat(str(updated_at))
        requirements = cls._requirements(item)
        return ApplicationContext(
            application_id=str(application_id_from_api),
            audience=audience,
            brokerage_slug=str(brokerage_slug),
            stage=stage,
            status=status,
            status_explanation=explanation,
            requirements=tuple(requirements),
            rmis=cls._verification(item.get("rmisVerification")),
            evident=cls._verification(item.get("evidentVerification")),
            training=cls._training(item),
            context_updated_at=context_updated_at.astimezone(UTC),
        )

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value)).astimezone(UTC)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _verification(cls, value: Any) -> VerificationSummary | None:
        if not isinstance(value, dict):
            return None
        raw = str(value.get("status") or "unknown").lower()
        states = {
            "invited": RequirementState.INVITED,
            "submitted": RequirementState.SUBMITTED,
            "processing": RequirementState.PROCESSING,
            "completed": RequirementState.SATISFIED,
            "passed": RequirementState.SATISFIED,
            "manually_approved": RequirementState.SATISFIED,
            "failed": RequirementState.FAILED,
            "timeout": RequirementState.FAILED,
        }
        state = states.get(raw, RequirementState.UNKNOWN)
        return VerificationSummary(
            state=state,
            updated_at=cls._parse_time(value.get("updatedAt") or value.get("updated_at")),
            action_required=state in {RequirementState.INVITED, RequirementState.FAILED},
        )

    @classmethod
    def _training(cls, item: dict[str, Any]) -> VerificationSummary | None:
        flags = ("safelandRequired", "w9Required", "h2sRequired")
        if not any(item.get(flag) for flag in flags):
            return None
        complete = all(
            not item.get(required) or bool(item.get(completed))
            for required, completed in (
                ("safelandRequired", "safelandCompletedAt"),
                ("w9Required", "w9ReceivedAt"),
                ("h2sRequired", "h2sCompletedAt"),
            )
        )
        return VerificationSummary(
            state=RequirementState.SATISFIED if complete else RequirementState.REQUIRED,
            action_required=not complete,
        )

    @classmethod
    def _requirements(cls, item: dict[str, Any]) -> list[Requirement]:
        requirements: list[Requirement] = []
        for key, label, required_key, complete_key in (
            ("safeland", "Safeland / PEC training", "safelandRequired", "safelandCompletedAt"),
            ("w9", "W-9", "w9Required", "w9ReceivedAt"),
            ("h2s", "H2S training", "h2sRequired", "h2sCompletedAt"),
        ):
            if not item.get(required_key):
                continue
            completed = cls._parse_time(item.get(complete_key))
            requirements.append(
                Requirement(
                    key=key,
                    label=label,
                    state=RequirementState.SATISFIED if completed else RequirementState.REQUIRED,
                    blocking=completed is None,
                    updated_at=completed,
                )
            )
        return requirements
