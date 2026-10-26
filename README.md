# django-auth-headless

Reusable Django authentication built on django-allauth Headless.

The first release focuses on Google OAuth, session authentication, CSRF/CORS
configuration, and setup and verification commands. The package is designed
for Django projects using any browser frontend. It does not include a frontend
or example application.

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

## Configure Django

In `settings.py`, import the package settings from `django_auth_headless.conf` and
assign them to the corresponding Django settings:

```python
from django_auth_headless.conf import *
```

Keep project-specific `SECRET_KEY`, `DEBUG`, `DATABASES`, `TEMPLATES`,
`ROOT_URLCONF`, `WSGI_APPLICATION`, `STATIC_URL`, `ALLOWED_HOSTS`, and email
settings in your project.

The exported `INSTALLED_APPS` already includes `django_auth_headless`, so Django
discovers the package and its management commands. Do not add it a second
time.

Add the package URLs to your project URL configuration:

```python
from django_auth_headless.urls import urlpatterns as auth_urlpatterns

urlpatterns = [
    *auth_urlpatterns,
]
```

Run migrations after installing and configuring the package:

```bash
python manage.py migrate
```

## Environment

Create a `.env` file beside `manage.py`:

```dotenv
DJANGO_FRONTEND_URL=http://localhost:5173
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173
DJANGO_AUTH_PROVIDERS=google
DJANGO_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
DJANGO_GOOGLE_CLIENT_SECRET=your-client-secret
```

Security settings are also environment-driven:

```dotenv
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SECURE_HSTS_SECONDS=0
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False
DJANGO_SECURE_HSTS_PRELOAD=False
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DJANGO_SESSION_COOKIE_DOMAIN=
DJANGO_SESSION_COOKIE_SAMESITE=Lax
DJANGO_CSRF_COOKIE_SAMESITE=Lax
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS=3600
```

Use secure cookies, HTTPS redirect, HSTS, and a production email backend in
production.

### Production domain routing

The default `Lax` cookies work when the frontend and backend are same-site,
such as `app.example.com` and `api.example.com`. For that deployment, set:

```dotenv
DJANGO_SESSION_COOKIE_DOMAIN=.example.com
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.example.com
DJANGO_CORS_ALLOWED_ORIGINS=https://app.example.com
```

The leading dot allows the session cookie to be sent to both subdomains.
Never set it to a domain you do not control.

If the frontend and backend are unrelated sites, such as
`myfrontend.vercel.app` and `mybackend.railway.app`, `SESSION_COOKIE_DOMAIN`
cannot bridge them. `SameSite=None` additionally requires `Secure`, and
browsers may still block third-party cookies. Use one custom parent domain or
route both applications through one reverse proxy. This package intentionally
uses browser sessions and does not silently replace them with client-side
tokens.

## Separate frontend and backend hosts

For unrelated hosts, use the package's database-backed bearer-token flow
instead of browser session cookies:

1. Set `DJANGO_FRONTEND_URL` to the frontend origin.
2. Configure the frontend to start OAuth with a callback to
   `/api/auth/callback`.
3. Apply migrations so the package can store hashed, expiring tokens.
4. After OAuth, Django redirects to the frontend with a short-lived token.
5. Send it as `Authorization: Bearer <token>` to `/api/me`.

The package stores only a hash of each token. Tokens expire according to
`DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS` and can be revoked with
`POST /api/auth/token/revoke`. Frontends should keep the access token in
memory, not localStorage or sessionStorage, and remove it from the URL
immediately after reading it.

## Management commands

The commands are available after `django_auth_headless` is included through the
exported `INSTALLED_APPS` list and migrations have been applied.

### Configure a provider

`setup_oauth` creates or updates the database-backed `SocialApp`, associates it
with the configured Site, and can write credentials to an env file.

```bash
# Interactive
python manage.py setup_oauth

# Non-interactive
python manage.py setup_oauth \
  --provider google \
  --client-id "$DJANGO_GOOGLE_CLIENT_ID" \
  --client-secret "$DJANGO_GOOGLE_CLIENT_SECRET" \
  --domain localhost:8000

# Also update an env file
python manage.py setup_oauth --env-file .env
```

Options: `--provider`, `--client-id`, `--client-secret`, `--domain`, `--name`,
and `--env-file`.

### Verify configuration

```bash
python manage.py verify_oauth
```

This checks the Site, database `SocialApp` records, provider environment
variables, and the allauth Headless configuration endpoint.

Provider credentials have one source of truth: the database `SocialApp`.
Environment variables supply credentials to `setup_oauth`; they are not also
registered as settings-backed provider applications.

## Endpoints

The package includes:

- `/_allauth/browser/v1/` — django-allauth Headless endpoints.
- `/accounts/` — provider callback routes.
- `/api/me` — authenticated current-user response.

`GET /api/me` returns:

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

## Development

```bash
uv sync --group dev
uv run python manage.py test
uv build
```

## Publishing

Releases are published to PyPI by the `Publish package` GitHub Actions
workflow when a GitHub Release is published. Configure PyPI Trusted Publishing
for the `bella-247/django-auth-headless` repository with:

- Workflow: `.github/workflows/publish.yml`
- Environment: `pypi`
- PyPI project: `django-auth-headless`

Update the version in `pyproject.toml`, push a matching tag, and publish a
GitHub Release for that tag. PyPI versions are immutable, so each release must
use a new version number.

## Scope

This is a Django-only package extracted from a Google OAuth learning project.
Provider configuration is extensible, but Google OAuth is the documented and
tested browser flow. The learning project is kept separate as an example.
