# Carrier Hub contract

## Internal callers

Carrier Hub sends its existing Firebase bearer token to `POST /v1/answer`. The KB validates the token indirectly by calling Carrier Hub's authenticated `GET /api/v1/user_info`, then permits only `internal`, `admin`, or `carrier-admin` roles. Browser role claims are never trusted directly.

## Public enrollment callers

The public registration-status and driver-enrollment pages do not have Firebase sessions. Before calling the KB, Carrier Hub must validate its own application-link authority and mint a short-lived JWT with:

```json
{
  "iss": "carrier-onboarding-server",
  "aud": "carrier-onboarding-kb",
  "sub": "non-PII-session-id",
  "scope": "carrier_public",
  "application_id": "optional verified application UUID",
  "exp": "five minutes or less"
}
```

The initial capability is deliberately restricted to `carrier_public`. Application-specific tools are a later, separately authorized contract.

## Future live tools

Implement one explicit Carrier Hub endpoint per question type, e.g. `GET /api/v1/kb-context/applications/{id}/next-step`. The KB passes the verified scope; Carrier Hub rechecks it. Do not give the KB a general database credential or a generic application API.
