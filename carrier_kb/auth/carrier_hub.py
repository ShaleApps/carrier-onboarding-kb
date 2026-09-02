"""Authentication lanes owned by Carrier Hub's trust model.

Internal requests carry the normal Firebase bearer token. This service asks Carrier
Hub's existing `/api/v1/user_info` endpoint to validate it and derive roles.
Public enrollment pages must exchange their application-link authority for a short
lived capability token server-side. A browser may never nominate its own audience,
application, or brokerage scope.
"""
from __future__ import annotations

import httpx
import jwt
from fastapi import HTTPException, Request, status

from carrier_kb.domain import Audience, Principal
from carrier_kb.settings import Settings


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class CarrierHubAuthorizer:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def principal(self, request: Request) -> Principal:
        raw = request.headers.get("authorization", "")
        if not raw.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bearer token required")
        token = raw[7:].strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bearer token required")

        capability = self._try_capability(token)
        if capability is not None:
            return capability
        return await self._internal_principal(token)

    def _try_capability(self, token: str) -> Principal | None:
        if not self.settings.kb_capability_secret:
            return None
        try:
            claims = jwt.decode(
                token,
                self.settings.kb_capability_secret,
                algorithms=["HS256"],
                audience=self.settings.kb_capability_audience,
                issuer=self.settings.kb_capability_issuer,
            )
        except jwt.PyJWTError:
            return None
        if claims.get("scope") != "carrier_public" or not claims.get("sub"):
            raise _forbidden("invalid carrier capability")
        return Principal(
            subject=str(claims["sub"]),
            audience=Audience.CARRIER,
            application_id=claims.get("application_id"),
            brokerage_id=claims.get("brokerage_id"),
        )

    async def _internal_principal(self, token: str) -> Principal:
        url = self.settings.carrier_hub_api_base_url.rstrip("/") + "/api/v1/user_info"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Carrier Hub authorization unavailable") from exc
        if response.status_code in (401, 403):
            raise _forbidden("not authorized")
        if response.status_code != 200:
            raise HTTPException(status_code=503, detail="Carrier Hub authorization unavailable")
        item = response.json().get("item") or {}
        roles = set(item.get("roles") or [])
        if not ({"internal", "admin", "carrier-admin"} & roles):
            raise _forbidden("internal Carrier Hub role required")
        subject = item.get("authId") or item.get("id")
        if not subject:
            raise _forbidden("invalid Carrier Hub identity")
        return Principal(subject=str(subject), audience=Audience.INTERNAL)
