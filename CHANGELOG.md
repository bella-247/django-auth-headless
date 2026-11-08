# Changelog

## 0.3.0 - 2026-11-09

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
