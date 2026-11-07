# Custom User Model & Universal Bearer Auth Design

## Intent & Why

`django-auth-headless` makes third-party OAuth and headless authentication effortless in Django. However, v0.2.0 made rigid assumptions that break in real-world Django projects:
1. It crashed on custom user models lacking standard `username` or `email` fields.
2. In cross-domain mode, Bearer tokens only authenticated `/api/me`, leaving custom application views with `AnonymousUser`.
3. The `from conf import *` pattern made registering custom user apps fragile.

This design generalizes user model handling, provides universal bearer authentication across all views via middleware, introduces modular `*AUTH_APPS` and `*AUTH_MIDDLEWARE` settings, and enables configurable user serialization for modern frontends.

---

## Goals, Non-Goals & Anti-Goals

### Goals
- **Universal Bearer Authentication**: Requests with `Authorization: Bearer <token>` automatically authenticate `request.user` across all project views, Ninja endpoints, and DRF views.
- **Custom User Agnostic**: The library works transparently with any `AUTH_USER_MODEL`, including email-only models (`USERNAME_FIELD = "email"`), UUID primary keys, and models without standard field names.
- **Modular Settings Integration**: Export `AUTH_APPS` and `AUTH_MIDDLEWARE` so developers can unpack them into their existing settings with Python's `*` operator without overwriting project configurations.
- **Configurable `/api/me` Payload**: Support safe default user profile serialization including connected providers, plus a pluggable `DJANGO_AUTH_USER_SERIALIZER` callable setting for custom frontend payloads.

### Non-Goals
- Building a full REST Framework or GraphQL replacement.
- Managing database migrations for external custom user models.

### Anti-Goals
- Breaking existing v0.2.0 imports or configuration for existing users.
- Re-implementing OAuth flows already handled by `django-allauth`.

---

## Architecture & Approaches

### Approaches Considered

1. **Option A: Safe Introspection + Pluggable Serializer + Global Bearer Middleware (Selected)**:
   - Safe attribute introspection (`get_user_model()`, `get_email_field_name()`, `getattr`).
   - `BearerTokenMiddleware` sitting after Django's `AuthenticationMiddleware`.
   - Pluggable `DJANGO_AUTH_USER_SERIALIZER` setting.
   - `AUTH_APPS` and `AUTH_MIDDLEWARE` exports.
   - Preserves backward compatibility while unlocking custom user and cross-domain architectures.

2. **Option B: Allauth Pure Delegation**:
   - Drop `/api/me` and force projects to implement custom token middleware and serializers.
   - Rejected: Defeats the library's mission of making third-party auth effortless.

---

## Detailed Design

### 1. `BearerTokenMiddleware`
Located at `src/django_auth_headless/middleware.py`:
- `__call__(request)`:
  - If `request.user` is already authenticated (e.g. session), proceed.
  - If `request.headers.get("Authorization", "").startswith("Bearer ")`:
    - Extract raw token, call `AccessToken.authenticate(raw_token)`.
    - If valid, assign `request.user = user`.
  - If token is invalid or missing, leave `request.user = AnonymousUser`.

### 2. Modular Settings in `conf.py`
Export:
- `AUTH_APPS = [...]` (allauth apps, corsheaders, django_auth_headless)
- `AUTH_MIDDLEWARE = ["allauth.account.middleware.AccountMiddleware", "django_auth_headless.middleware.BearerTokenMiddleware"]`
- Retain existing `INSTALLED_APPS` and `MIDDLEWARE` exports for backward compatibility.

### 3. Safe Social Account Adapter
In `src/django_auth_headless/adapters.py`:
- Determine email field via `user.get_email_field_name()` if available or fallback to `"email"`.
- Verify user model has the field before accessing or saving with `update_fields`.
- Only execute `user.save(update_fields=[...])` if `user.pk` is not None.

### 4. Flexible `/api/me` Endpoint
In `src/django_auth_headless/views.py`:
- Check for `DJANGO_AUTH_USER_SERIALIZER` in settings:
  - If configured as import string (e.g. `"myapp.users.serializers.get_user_data"`), call it with `user`.
  - Otherwise, default to safe dictionary:
    - `id`: `user.pk`
    - `username`: `user.get_username()`
    - `email`: safely resolved email
    - `connected_providers`: list of provider IDs linked via `SocialAccount`

