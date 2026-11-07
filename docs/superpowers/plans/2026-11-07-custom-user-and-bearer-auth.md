# Custom User Model & Universal Bearer Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable universal Bearer token authentication across all Django views and make the library resilient to any custom user model while providing a configurable user serialization endpoint.

**Architecture:** A lightweight `BearerTokenMiddleware` intercepts `Authorization: Bearer <token>` and populates `request.user` globally. Modular `*AUTH_APPS` and `*AUTH_MIDDLEWARE` lists are exported for clean unpacking in `settings.py`. Safe attribute introspection and a `DJANGO_AUTH_USER_SERIALIZER` setting allow arbitrary user model shapes and customized frontend payloads.

**Tech Stack:** Python 3.13+, Django 6.1+, django-allauth, hatchling/uv.

**Spec:** docs/superpowers/specs/2026-11-07-custom-user-and-bearer-auth-design.md

## Global Constraints

- Requires Python >= 3.13 and Django >= 6.1.
- All existing v0.2.0 imports (`from django_auth_headless.conf import *`) must remain backward-compatible.
- No direct attribute crashes on user models lacking `email` or `username`.
- Cross-domain bearer tokens must authenticate standard Django views without requiring manual view-level code.

## Review Focus

- Request with malformed Authorization header (e.g. `Bearer` with empty string or invalid padding) leaves `request.user` as `AnonymousUser` without throwing 500.
- Custom user model with `USERNAME_FIELD = "email"` and no `username` field does not crash `/api/me`.
- User model without an `email` field does not crash `AuthenticationSocialAccountAdapter` or `/api/me`.
- Expired or revoked `AccessToken` leaves `request.user` as `AnonymousUser` in middleware.
- Custom serializer configured in `DJANGO_AUTH_USER_SERIALIZER` as an import string is invoked and its output returned by `/api/me`.

---

### Task 1: BearerTokenMiddleware and Modular Settings Exports

**Files:**
- Create: `src/django_auth_headless/middleware.py`
- Modify: `src/django_auth_headless/conf.py`
- Test: `tests/test_middleware.py`

**Interfaces:**
- Produces: `BearerTokenMiddleware(get_response)` in `src/django_auth_headless/middleware.py`
- Produces: `AUTH_APPS` and `AUTH_MIDDLEWARE` exports in `src/django_auth_headless/conf.py`

- [ ] **Step 1: Write failing tests for `BearerTokenMiddleware`**

```python
# tests/test_middleware.py
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django_auth_headless.models import AccessToken
from django_auth_headless.middleware import BearerTokenMiddleware

class BearerTokenMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="mw-user", email="mw@example.com", password="password"
        )
        self.middleware = BearerTokenMiddleware(lambda req: HttpResponse(req.user.get_username()))

    def test_valid_bearer_token_sets_request_user(self):
        _, raw_token = AccessToken.issue(self.user, timedelta(minutes=10))
        request = self.factory.get("/any/endpoint", HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.user, self.user)

    def test_invalid_bearer_token_leaves_anonymous_user(self):
        request = self.factory.get("/any/endpoint", HTTP_AUTHORIZATION="Bearer invalid-token")
        request.user = AnonymousUser()
        self.middleware(request)
        self.assertTrue(request.user.is_anonymous)

    def test_already_authenticated_user_preserved(self):
        request = self.factory.get("/any/endpoint")
        request.user = self.user
        self.middleware(request)
        self.assertEqual(request.user, self.user)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python manage.py test tests.test_middleware`
Expected: FAIL with `ModuleNotFoundError: No module named 'django_auth_headless.middleware'`

- [ ] **Step 3: Implement `BearerTokenMiddleware` and modular exports**

In `src/django_auth_headless/middleware.py`:
Implement `BearerTokenMiddleware` extracting `Authorization: Bearer <token>`, calling `AccessToken.authenticate(token)`, and setting `request.user` if unauthenticated.

In `src/django_auth_headless/conf.py`:
Define and export:
- `AUTH_APPS = ["allauth", "allauth.account", "allauth.socialaccount", "allauth.socialaccount.providers.google", "allauth.socialaccount.providers.github", "allauth.socialaccount.providers.gitlab", "allauth.socialaccount.providers.microsoft", "allauth.headless", "corsheaders", AUTHENTICATION_PACKAGE]`
- `AUTH_MIDDLEWARE = ["allauth.account.middleware.AccountMiddleware", f"{AUTHENTICATION_PACKAGE}.middleware.BearerTokenMiddleware"]`
Include `BearerTokenMiddleware` in default exported `MIDDLEWARE`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python manage.py test tests.test_middleware`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/django_auth_headless/middleware.py src/django_auth_headless/conf.py tests/test_middleware.py
git commit -m "feat: add BearerTokenMiddleware and modular settings exports"
```

---

### Task 2: Custom User Resilience in Social Account Adapter

**Files:**
- Modify: `src/django_auth_headless/adapters.py`
- Test: `tests/test_adapter.py`

**Interfaces:**
- Consumes: `DefaultSocialAccountAdapter` from allauth
- Produces: `AuthenticationSocialAccountAdapter.pre_social_login` handling user models without an `email` field or during pre-save stage safely.

- [ ] **Step 1: Write failing tests for adapter user introspection**

```python
# tests/test_adapter.py
from unittest.mock import MagicMock
from django.test import TestCase
from django_auth_headless.adapters import AuthenticationSocialAccountAdapter

class MockUserWithoutEmail:
    pk = 1
    # Note: no email attribute

class MockEmailOnlyUser:
    pk = 1
    email = ""

class AdapterUserTests(TestCase):
    def test_pre_social_login_ignores_user_without_email_attribute(self):
        adapter = AuthenticationSocialAccountAdapter()
        user = MockUserWithoutEmail()
        sociallogin = MagicMock()
        sociallogin.user = user
        sociallogin.account.extra_data = {"email": "provider@example.com"}
        request = MagicMock()
        # Should not raise AttributeError
        adapter.pre_social_login(request, sociallogin)

    def test_pre_social_login_populates_empty_email_when_supported(self):
        adapter = AuthenticationSocialAccountAdapter()
        user = MockEmailOnlyUser()
        user.save = MagicMock()
        sociallogin = MagicMock()
        sociallogin.user = user
        sociallogin.account.extra_data = {"email": "provider@example.com"}
        request = MagicMock()
        adapter.pre_social_login(request, sociallogin)
        self.assertEqual(user.email, "provider@example.com")
        user.save.assert_called_once_with(update_fields=["email"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python manage.py test tests.test_adapter`
Expected: FAIL with `AttributeError: 'MockUserWithoutEmail' object has no attribute 'email'`

- [ ] **Step 3: Implement safe user attribute introspection in `adapters.py`**

In `src/django_auth_headless/adapters.py`:
- Use `getattr(user, "get_email_field_name", None)` to find email field name, defaulting to `"email"`.
- Check `hasattr(user, email_field)`.
- If field exists, read and set it safely.
- Only call `user.save(update_fields=[email_field])` if `getattr(user, "pk", None)` is not None and field exists in model's fields.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python manage.py test tests.test_adapter`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/django_auth_headless/adapters.py tests/test_adapter.py
git commit -m "fix: make social account adapter resilient to custom user models"
```

---

### Task 3: Configurable `/api/me` with Connected Providers and Custom Serializer

**Files:**
- Modify: `src/django_auth_headless/views.py`
- Test: `tests/test_current_user.py`

**Interfaces:**
- Produces: `current_user(request)` supporting safe email extraction, `connected_providers`, and optional `DJANGO_AUTH_USER_SERIALIZER` callable.

- [ ] **Step 1: Write failing tests for `/api/me` features**

```python
# tests/test_current_user.py
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from allauth.socialaccount.models import SocialApp, SocialAccount
from django.contrib.sites.models import Site

def custom_serializer(user):
    return {"custom_id": user.pk, "role": "admin"}

class CurrentUserEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="me-user", email="me@example.com", password="password"
        )
        self.client.force_login(self.user)

    def test_me_returns_connected_providers(self):
        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="google-12345",
            extra_data={"email": "me@example.com"},
        )
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]["user"]
        self.assertIn("google", data["connected_providers"])

    @override_settings(DJANGO_AUTH_USER_SERIALIZER="tests.test_current_user.custom_serializer")
    def test_custom_user_serializer_invoked(self):
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]["user"]
        self.assertEqual(data["custom_id"], self.user.pk)
        self.assertEqual(data["role"], "admin")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python manage.py test tests.test_current_user`
Expected: FAIL with `KeyError: 'connected_providers'`

- [ ] **Step 3: Update `current_user` in `src/django_auth_headless/views.py`**

- Use `django.utils.module_loading.import_string` to load `DJANGO_AUTH_USER_SERIALIZER` if configured in `django.conf.settings`.
- If serializer is configured, invoke it with `user` and return the result in `"user"`.
- If not configured, safely build default dictionary:
  - `id`: `user.pk`
  - `username`: `user.get_username()`
  - `email`: `getattr(user, getattr(user, "get_email_field_name", lambda: "email")(), "")`
  - `connected_providers`: list of unique provider IDs from `SocialAccount.objects.filter(user=user).values_list("provider", flat=True)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python manage.py test tests.test_current_user`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/django_auth_headless/views.py tests/test_current_user.py
git commit -m "feat: add connected_providers and custom user serializer to /api/me"
```

---

### Task 4: Documentation, Package Version Bump, and Build Verification

**Files:**
- Modify: `docs/setup.md`
- Modify: `pyproject.toml`
- Modify: `CHANGELOG.md`
- Modify: `README.md`

- [ ] **Step 1: Update documentation for modular unpacking & custom users**
Update `docs/setup.md` and `README.md` to showcase `from django_auth_headless.conf import AUTH_APPS, AUTH_MIDDLEWARE`, `*AUTH_APPS`, `*AUTH_MIDDLEWARE`, and `DJANGO_AUTH_USER_SERIALIZER`.

- [ ] **Step 2: Bump version to 0.3.0 in `pyproject.toml` and record in `CHANGELOG.md`**
Bump `version = "0.3.0"` in `pyproject.toml`.
Add `## 0.3.0` section in `CHANGELOG.md`.

- [ ] **Step 3: Run entire test suite and verify build**
Run: `uv run python manage.py test`
Expected: 100% PASS across all tests.
Run: `uv build && uvx twine check dist/*`
Expected: Clean wheel and sdist for 0.3.0 created and passing twine check.

- [ ] **Step 4: Commit**

```bash
git add docs/ pyproject.toml CHANGELOG.md README.md dist/
git commit -m "chore: release 0.3.0 with custom user support and modular middleware"
```

