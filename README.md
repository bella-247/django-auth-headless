# django-allauth-cross-domain

OAuth cross-domain authentication bridge and bearer tokens for django-allauth Headless.

`django-allauth-cross-domain` solves OAuth authentication for decoupled architectures
where the frontend (React, Next.js, Vue, mobile) and Django backend run on separate
domains. It keeps django-allauth as the authentication engine and adds a secure,
one-time authorization code exchange with PKCE, refresh token rotation, and bearer token
authentication for plain Django views, DRF, and Django Ninja.

The package exists because connecting a decoupled frontend to a Django API across
unrelated origins often breaks standard cookie authentication (Safari ITP, cross-origin cookie blocks).
This library provides a hardened handoff bridge and zero-admin setup tools without taking ownership
of the consuming application's users or database.

The original learning project, including its React frontend, is available at
https://github.com/bella-247/DjangoOAuth.

## Install

```bash
pip install django-allauth-cross-domain
# or
uv add django-allauth-cross-domain

# With DRF or Ninja support:
pip install "django-allauth-cross-domain[drf]"
pip install "django-allauth-cross-domain[ninja]"
```

The package requires Python >=3.10, Django >=4.2, django-allauth with the `headless` and
`socialaccount` extras, django-cors-headers, and python-dotenv.

## Quick start

```bash
pip install django-allauth-cross-domain
python manage.py migrate
python manage.py setup_oauth --provider google
python manage.py verify_oauth
```

Then configure the required settings and URLs described in
[docs/setup.md](docs/setup.md). For a complete working frontend, see the
[DjangoOAuth learning project](https://github.com/bella-247/DjangoOAuth).

## Configure Django

In `settings.py`, unpack the modular app and middleware lists, and define `DJANGO_AUTH`:

```python
from django_allauth_cross_domain.conf import (
    AUTH_APPS,
    AUTH_MIDDLEWARE,
    CORS_MIDDLEWARE,
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # "users",  # Your custom user model app
    "corsheaders",
    *AUTH_APPS,
]

MIDDLEWARE = [
    CORS_MIDDLEWARE,
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    *AUTH_MIDDLEWARE,  # Injects allauth AccountMiddleware & BearerTokenMiddleware
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Unified authentication settings
DJANGO_AUTH = {
    "FRONTEND_URL": "http://localhost:5173",
    "MODE": "cross-domain",  # "session" or "cross-domain"
    "PROVIDERS": ["google", "github", "apple"],
    "EMAIL_VERIFICATION": "mandatory",  # "mandatory" | "optional" | "none"
    "EMAIL_AUTO_CONNECT": False,        # Prevents OAuth pre-hijacking
    "ACCESS_TOKEN_LIFETIME_SECONDS": 3600,
    "REFRESH_TOKEN_LIFETIME_SECONDS": 2592000,  # 30 days
    "ROTATE_REFRESH_TOKENS": True,
}
```

Add the package URLs:

```python
from django_allauth_cross_domain.urls import urlpatterns as auth_urlpatterns

urlpatterns = [
    *auth_urlpatterns,
]
```

## Documentation

- [Setup guide](docs/setup.md)
- [Architecture and authentication modes](docs/architecture.md)
- [Deployment and security](docs/deployment.md)
- [API reference](docs/api.md)
- [Comparison with alternatives](docs/comparisons.md)
- [Contributing](docs/contributing.md)
- [Guidance for AI coding agents](docs/agent-guidance.md)
- [Changelog](CHANGELOG.md)

## Environment

```dotenv
DJANGO_FRONTEND_URL=http://localhost:5173
DJANGO_AUTH_MODE=session
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173
DJANGO_AUTH_PROVIDERS=google
DJANGO_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
DJANGO_GOOGLE_CLIENT_SECRET=your-client-secret
DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS=3600
```

Do not commit the real `.env` file.

Use `DJANGO_AUTH_MODE=session` for same-site deployments. For unrelated
frontend and backend domains, set `DJANGO_AUTH_MODE=cross-domain` to enable
the one-time authorization-code exchange and in-memory bearer tokens. The
token callback, exchange, and revocation endpoints are disabled in session
mode.

## Management commands

```bash
python manage.py setup_oauth --provider google
python manage.py verify_oauth
```

`setup_oauth` creates or updates the database-backed `SocialApp`, associates
it with the configured Site, and can write credentials to an env file.
`verify_oauth` checks the Site, SocialApp records, environment variables, and
the allauth Headless configuration endpoint.

Provider credentials have one source of truth: the database `SocialApp`.
Environment variables supply credentials to setup and verification; they are
not also registered as settings-backed provider applications.

## Endpoints

- `/_allauth/browser/v1/` — django-allauth Headless endpoints.
- `/accounts/` — provider callback routes.
- `/api/me` — authenticated current-user response.
- `/api/auth/exchange` — one-time-code exchange for separate hosts.
- `/api/auth/token/revoke` — bearer-token revocation.

## Development

```bash
uv sync --group dev
uv run python manage.py test
uv build
```

## Contributing

Contributions are welcome. Read [docs/contributing.md](docs/contributing.md)
before opening an issue or pull request. Never include OAuth secrets, cookies,
access tokens, or personal data in issues, logs, or commits.

## Publishing

Releases are published to PyPI by the `Publish package` GitHub Actions
workflow when a GitHub Release is published. Configure PyPI Trusted Publishing
for the `bella-247/django-allauth-cross-domain` repository with the `pypi`
environment. PyPI versions are immutable, so each release must use a new
version number.

## Scope and limitations

This is a Django-only package extracted from a Google OAuth learning project.
Provider configuration is extensible, but Google OAuth is the documented and
tested browser flow. It does not include React code or an example application.
