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

The capability is deliberately restricted to `carrier_public`. Its optional
`application_id` is the only accepted application scope: the request body has
no application-ID field and rejects one if supplied.

## Implemented live status tool

For an application-scoped request, the KB calls the existing read-only endpoint:

```text
GET /api/v1/application/{verified_application_id}/status
```

It passes the capability bearer token. Carrier Hub remains responsible for
rechecking that authority. The KB projects the response into a small status
card (stage, status, safe requirement states, next action, and update time),
not raw application data. Public capabilities always request Carrier Hub's
public projection; internal callers request the internal projection.

Do not give the KB a general Carrier Hub database credential or generic
application API. Add any future live capability as a separate, typed,
read-only contract with explicit field allowlisting.
