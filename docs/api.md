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
      "email": "example@example.com"
    }
  }
}
```

Unauthenticated requests return HTTP 401.

## `GET /api/auth/callback`

The separate-host callback creates a five-minute handoff code and redirects
to `DJANGO_FRONTEND_URL` using a URL fragment. The code is not an access token
and can be redeemed only once.

## `POST /api/auth/exchange`

Request:

```json
{"code": "one-time-handoff-code"}
```

Success:

```json
{
  "status": 200,
  "data": {
    "access_token": "opaque-token",
    "expires_in": 3600
  }
}
```

Invalid or expired codes return HTTP 400.

## `POST /api/auth/token/revoke`

Revokes the bearer token in the `Authorization` header and returns HTTP 204.
