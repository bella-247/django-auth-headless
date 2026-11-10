# API reference

The package includes django-allauth Headless routes plus these integration
endpoints.

## `GET /api/me`

Accepts either the Django session cookie or:

```http
Authorization: Bearer <access-token>
```

Success:

```json
{
  "status": 200,
  "data": {
    "user": {
      "id": 1,
      "username": "example",
      "email": "example@example.com",
      "connected_providers": ["google"]
    }
  }
}
```

To customize this payload or return custom user profile fields, configure `DJANGO_AUTH_USER_SERIALIZER` in your `settings.py`.

Unauthenticated requests return HTTP 401.

## `GET /api/auth/callback`

When `DJANGO_AUTH_MODE=cross-domain`, the separate-host callback creates a
single-use handoff code (default 60 seconds lifetime) and redirects to
`DJANGO_FRONTEND_URL` using a URL fragment. The code is not an access token and
can be redeemed only once.

### PKCE Parameters (RFC 7636)
You can optionally bind the handoff code to an in-memory client secret:
- `code_challenge`: Base64URL-encoded SHA256 hash of your frontend verifier.
- `code_challenge_method`: `S256` (default) or `plain`.

If `DJANGO_AUTH["ENFORCE_PKCE"] = True`, requests without a `code_challenge` return HTTP 400.

## `POST /api/auth/exchange`

Redeems a single-use authorization code for active access and refresh tokens.

Request:

```json
{
  "code": "one-time-handoff-code",
  "code_verifier": "secret-stored-only-in-frontend-memory"
}
```

> **Note:** If `code_challenge` was registered at issuance, `code_verifier` is strictly mandatory. Without it, redemption is immediately rejected, rendering stolen authorization codes useless to adversaries.

Success:

```json
{
  "status": 200,
  "data": {
    "access_token": "opaque-access-token",
    "refresh_token": "opaque-refresh-token",
    "expires_in": 3600
  }
}
```

Invalid or expired codes return HTTP 400. The endpoint returns HTTP 404 when
`DJANGO_AUTH_MODE=session`.

## `POST /api/auth/refresh` (or `/api/auth/token/refresh`)

Rotates an active refresh token to obtain a fresh access token without re-authenticating.

Request:

```json
{
  "refresh_token": "opaque-refresh-token"
}
```

Success:

```json
{
  "status": 200,
  "data": {
    "access_token": "new-opaque-access-token",
    "refresh_token": "new-rotated-refresh-token",
    "expires_in": 3600
  }
}
```

Invalid, revoked, or expired refresh tokens return HTTP 401.

## `POST /api/auth/token/revoke`

Revokes a bearer token in the `Authorization` header, or revokes an access/refresh token passed in the request body:

```json
{
  "token": "opaque-token-to-revoke"
}
```

Returns HTTP 204 on success. The endpoint returns HTTP 404 when `DJANGO_AUTH_MODE=session`.

