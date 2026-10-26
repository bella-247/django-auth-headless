# django-auth-headless

Reusable Django authentication built on django-allauth Headless.

`django-auth-headless` makes OAuth setup easier for Django applications with a
browser frontend. It keeps django-allauth as the authentication engine and
adds guided setup, verification, consistent configuration, and an optional
secure cross-domain authorization-code exchange.

The package exists because connecting a Django API to a React, Vue, or mobile
client often requires several unrelated configuration tasks: Sites,
SocialApps, callback URLs, CORS, CSRF, cookies, and frontend/backend domain
routing. This project puts those tasks behind a small, documented integration
surface without taking ownership of the consuming application's users,
database, or frontend.

The original learning project, including its React frontend, is available at
https://github.com/bella-247/DjangoOAuth.

## Install

```bash
pip install django-auth-headless
# or
uv add django-auth-headless
```

The package requires Django 6.1, django-allauth with the `headless` and
`socialaccount` extras, django-cors-headers, and python-dotenv.

## Quick start

```bash
pip install django-auth-headless
python manage.py migrate
python manage.py setup_oauth --provider google
python manage.py verify_oauth
```

Then configure the required settings and URLs described in
[docs/setup.md](docs/setup.md). For a complete working frontend, see the
[DjangoOAuth learning project](https://github.com/bella-247/DjangoOAuth).

## Configure Django

In `settings.py`, import the package settings from
`django_auth_headless.conf`:

```python
from django_auth_headless.conf import *
```

Keep project-specific `SECRET_KEY`, `DEBUG`, `DATABASES`, `TEMPLATES`,
`ROOT_URLCONF`, `WSGI_APPLICATION`, `STATIC_URL`, `ALLOWED_HOSTS`, and email
settings in your project.

The exported `INSTALLED_APPS` already includes `django_auth_headless`, so Django
discovers the package and its management commands. Do not add it a second
time.

Add the package URLs:

```python
from django_auth_headless.urls import urlpatterns as auth_urlpatterns

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
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173
DJANGO_AUTH_PROVIDERS=google
DJANGO_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
DJANGO_GOOGLE_CLIENT_SECRET=your-client-secret
DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS=3600
```

Do not commit the real `.env` file.

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
for the `bella-247/django-auth-headless` repository with the `pypi`
environment. PyPI versions are immutable, so each release must use a new
version number.

## Scope and limitations

This is a Django-only package extracted from a Google OAuth learning project.
Provider configuration is extensible, but Google OAuth is the documented and
tested browser flow. It does not include React code or an example application.
