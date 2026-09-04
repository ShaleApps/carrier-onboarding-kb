from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from carrier_kb.auth.carrier_hub import CarrierHubAuthorizer
from carrier_kb.domain import Audience
from carrier_kb.settings import Settings


def _capability(secret: str, **claims) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": "carrier-user",
            "scope": "carrier_public",
            "application_id": "application-from-token",
            "brokerage_id": "bainbridge",
            "iss": "carrier-onboarding-server",
            "aud": "carrier-onboarding-kb",
            "iat": now,
            "exp": now + timedelta(minutes=10),
            **claims,
        },
        secret,
        algorithm="HS256",
    )


def test_capability_is_the_only_source_of_carrier_application_scope(monkeypatch):
    secret = "test-capability-secret-at-least-32-bytes"
    monkeypatch.setenv("KB_CAPABILITY_SECRET", secret)
    authorizer = CarrierHubAuthorizer(Settings())

    principal = authorizer._try_capability(_capability(secret))

    assert principal is not None
    assert principal.audience is Audience.CARRIER
    assert principal.application_id == "application-from-token"
    assert principal.brokerage_id == "bainbridge"


def test_capability_with_wrong_scope_is_denied(monkeypatch):
    secret = "test-capability-secret-at-least-32-bytes"
    monkeypatch.setenv("KB_CAPABILITY_SECRET", secret)
    authorizer = CarrierHubAuthorizer(Settings())

    token = _capability(secret, scope="carrier_internal")

    with pytest.raises(HTTPException) as exc_info:
        authorizer._try_capability(token)
    assert exc_info.value.status_code == 403
