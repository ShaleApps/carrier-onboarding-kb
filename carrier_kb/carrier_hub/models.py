from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ContextAudience(StrEnum):
    """The projection requested by the already-authorized caller."""

    PUBLIC = "public"
    INTERNAL = "internal"


class RequirementState(StrEnum):
    REQUIRED = "required"
    INVITED = "invited"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    SATISFIED = "satisfied"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class ActionActor(StrEnum):
    CARRIER = "carrier"
    INTERNAL = "internal"
    CARRIER_HUB = "carrier_hub"
    HUMAN_REVIEW = "human_review"


class Requirement(BaseModel):
    """A user-facing requirement, never a raw vendor payload."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    state: RequirementState
    explanation: str | None = Field(default=None, max_length=1000)
    due_at: datetime | None = None
    blocking: bool = False
    updated_at: datetime | None = None


class NextAction(BaseModel):
    """The single most useful next step for the caller."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1500)
    actor: ActionActor
    blocking: bool = False
    href: str | None = Field(default=None, max_length=1000)
    due_at: datetime | None = None
    generated_at: datetime


class VerificationSummary(BaseModel):
    """Safe summary of one verification family."""

    model_config = ConfigDict(extra="forbid")

    state: RequirementState
    updated_at: datetime | None = None
    action_required: bool = False


class DriverInvitationSummary(BaseModel):
    """PII-minimized driver invitation status."""

    model_config = ConfigDict(extra="forbid")

    invitation_id: str
    display_name: str
    state: str = Field(min_length=1, max_length=40)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApplicationContext(BaseModel):
    """Carrier Hub's KB-specific, audience-filtered read projection.

    Carrier Hub owns construction of this object. The KB must not reconstruct
    eligibility or next actions from raw application fields.
    """

    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(min_length=1, max_length=100)
    audience: ContextAudience
    brokerage_slug: str = Field(min_length=1, max_length=80)
    carrier_name: str | None = Field(default=None, max_length=200)
    stage: str = Field(min_length=1, max_length=80)
    status: str = Field(min_length=1, max_length=80)
    status_explanation: str | None = Field(default=None, max_length=1500)
    next_action: NextAction | None = None
    requirements: tuple[Requirement, ...] = ()
    rmis: VerificationSummary | None = None
    evident: VerificationSummary | None = None
    brs: VerificationSummary | None = None
    training: VerificationSummary | None = None
    docusign: VerificationSummary | None = None
    driver_invitations: tuple[DriverInvitationSummary, ...] = ()
    context_updated_at: datetime
    stale_after_seconds: int = Field(default=900, ge=0, le=86400)
