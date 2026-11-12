# Changelog

## 0.3.1 - 2026-11-10

- **Package Renaming (`django-allauth-cross-domain`)**: Renamed the package and Python module to `django-allauth-cross-domain` (`django_allauth_cross_domain`) to clearly establish its purpose as the cross-domain OAuth bridge for django-allauth Headless and eliminate confusion with allauth's built-in `headless` module.
- **Django REST Framework & Django Ninja Contrib Modules**:
  - `django_allauth_cross_domain.contrib.rest_framework.BearerTokenAuthentication`: Native DRF authenticator that validates Bearer access tokens without triggering DRF's session CSRF checks on mutating requests (POST/PUT/DELETE).
  - `django_allauth_cross_domain.contrib.ninja.BearerAuth`: Drop-in `HttpBearer` authenticator for Django Ninja endpoints.
- **Automatic Token Revocation on Password Change & Deactivation**: Added lifecycle signal receivers connected to allauth (`password_changed`, `password_reset`, `password_set`) and Django `post_save` to immediately invalidate all active access and refresh tokens when a user changes their password or is deactivated.
- **Database Performance & High-Volume Indexing**: Added `db_index=True` to `expires_at` on `AccessToken`, `RefreshToken`, and `OAuthHandoffCode` to prevent sequential table scans during `cleanup_tokens` runs.
- **Security Audit Logging**: Added structured logging (`logging.getLogger("django_allauth_cross_domain")`) on authentication failures, PKCE verifier mismatches, authorization code exchanges, and token lifecycle events.
- **PEP 561 Typing Marker (`py.typed`)**: Added type marker file allowing external type checkers (mypy, pyright, ruff) to verify typed consuming code.
- **Multi-Version GitHub Actions CI Matrix**: Expanded test workflows to test against Python 3.10, 3.11, 3.12, and 3.13.
- **PKCE-Style Code Verifier Protection (RFC 7636)**: Added full Proof Key for Code Exchange (PKCE) support to the cross-domain handoff flow. The frontend can provide a `code_challenge` (S256 or plain) at `/api/auth/callback`; `/api/auth/exchange` then requires the secret in-memory `code_verifier`. Possession of the authorization code alone is completely useless to an attacker. Added optional `ENFORCE_PKCE = True` setting.
- **Broadened Compatibility Matrix**: Expanded Python support to `>=3.10` (Python 3.10, 3.11, 3.12, 3.13) and Django support to `>=4.2` (Django 4.2 LTS, 5.0, 5.1).
- **Security Hardening on Bearer Authentication**: Enforced `is_active` validation across `AccessToken.authenticate`, `RefreshToken.authenticate`, `OAuthHandoffCode.redeem`, and `/api/me`. Inactive or deactivated users are immediately blocked from authenticating or refreshing tokens.
- **Shortened OAuth Handoff Code Lifetime**: Reduced single-use authorization code TTL from 5 minutes to 60 seconds (configurable via `HANDOFF_CODE_LIFETIME_SECONDS`) to minimize replay and intercept exposure.
- **HTTP Security Headers**: Added `Cache-Control: no-store` on `/api/auth/exchange` and `/api/auth/refresh` to prevent token caching in intermediaries/browsers, and `WWW-Authenticate: Bearer` on 401 responses.
- **CLI Security Enhancements**:
  - `setup_oauth`: Masked client secrets on stdout (`*** (hidden)`), enforced strict `0o600` file permissions when writing to `.env`, and added `apple` to supported provider choices.
  - `verify_oauth`: Dynamically introspects `site.domain` for `HTTP_HOST` and configured `FRONTEND_URL` for `HTTP_ORIGIN` instead of hardcoding `localhost:8000`.
- **Eliminated Runtime Settings Mutation**: Removed `setattr(settings, ...)` mutation from `AuthenticationConfig.ready()` to prevent silent clobbering of explicit user settings (e.g., `ACCOUNT_EMAIL_VERIFICATION = "none"`). Replaced with read-only Django security system checks.
- **Strict Boolean Parsing (`to_bool`)**: Fixed boolean inversion bug where string booleans like `"false"` or `"0"` evaluated truthy in Python, ensuring `EMAIL_AUTO_CONNECT`, `ROTATE_REFRESH_TOKENS`, and cookie secure flags are safely parsed.
- **Resolved Duplicate Application Label Conflict**: Removed `"corsheaders"` from `AUTH_APPS` so projects with `"corsheaders"` in `INSTALLED_APPS` don't encounter `ImproperlyConfigured: duplicate application label: corsheaders`.
- **Clean Package Distributions**: Excluded development harnesses and internal artifacts from source distributions (`sdist`). Verified via `twine check`.

## 0.3.0 - 2026-11-09

- **Refresh Token Rotation (`POST /api/auth/refresh`)**: Introduced `RefreshToken`
  model and silent token rotation flow. `/api/auth/exchange` returns both
  `access_token` and `refresh_token`, allowing frontends to refresh tokens
  in the background without re-authenticating. Supports automatic rotation via
  `ROTATE_REFRESH_TOKENS = True`.
- **Sign in with Apple Support**: Added Apple provider (`allauth.socialaccount.providers.apple`)
  to default supported providers, enabling iOS App Store Guideline 4.8 compliance.
- **Token Housekeeping (`manage.py cleanup_tokens`)**: Added maintenance command
  to purge expired `AccessToken`, `RefreshToken`, and `OAuthHandoffCode` records.
- **Unified `DJANGO_AUTH` Configuration & Security Controls**: Introduced DRF-style
  `DJANGO_AUTH = { ... }` settings dictionary with secure defaults (`EMAIL_VERIFICATION = "mandatory"`,
  and `EMAIL_AUTO_CONNECT = False` to prevent OAuth account pre-hijacking attacks).
- **Universal Bearer Token Authentication**: Added `BearerTokenMiddleware` to
  authenticate `Authorization: Bearer <token>` requests across all views, DRF
  endpoints, and Django Ninja routes without manual view-level code.
- **Modular Settings Integration**: Exported `AUTH_APPS`, `AUTH_MIDDLEWARE`, and
  `CORS_MIDDLEWARE` so developers can unpack them into their own `settings.py`
  without overwriting custom user apps or custom middlewares.
- **Custom User Model Resilience**: Made `AuthenticationSocialAccountAdapter`
  and `/api/me` resilient to any `AUTH_USER_MODEL`, safely handling models
  without an `email` field, custom email field names, and pre-save signup states.
- **Connected Providers on `/api/me`**: Added `connected_providers` list to
  `/api/me` so frontends can easily inspect all linked social accounts.
- **Pluggable User Serializer Hook**: Added `DJANGO_AUTH_USER_SERIALIZER` setting
  to allow applications to return custom user profile payloads to frontends.
- **Modular Architecture**: Extracted serialization logic into `serializers.py`
  and organized utilities into a structured `utils/` package.

## 0.2.0 - 2026-11-06

- Added durable documentation for setup, architecture, deployment, API usage,
  comparisons, contribution, and AI-assisted development.
- Added the secure cross-domain authorization-code exchange on the feature
  branch.
- Added explicit authentication mode configuration for cookie and bearer-token
  flows.

## 0.1.0

- Initial Django-only package extracted from the DjangoOAuth learning project.
- Added environment-based configuration, OAuth setup, and verification
  commands.
