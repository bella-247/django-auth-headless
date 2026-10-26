# Setup guide

This guide configures `django-auth-headless` in an existing Django project.

## Install and configure

```bash
pip install django-auth-headless
```

In `settings.py`, import the exported values from
`django_auth_headless.conf`. Keep project-specific values such as
`SECRET_KEY`, `DEBUG`, `DATABASES`, templates, URLs, static files, hosts,
password validators, and email delivery in the project.

The exported `INSTALLED_APPS` already contains `django_auth_headless`.
Including it twice can create confusing app and migration behavior.

Include the URLs:

```python
from django_auth_headless.urls import urlpatterns as auth_urlpatterns

urlpatterns = [*auth_urlpatterns]
```

Create `.env` beside `manage.py`:

```dotenv
DJANGO_FRONTEND_URL=http://localhost:5173
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173
DJANGO_AUTH_PROVIDERS=google
DJANGO_GOOGLE_CLIENT_ID=replace-me
DJANGO_GOOGLE_CLIENT_SECRET=replace-me
```

Do not commit the real `.env`.

## Configure Google

```bash
python manage.py migrate
python manage.py setup_oauth --provider google --domain localhost:8000
python manage.py verify_oauth
```

Add this exact redirect URI to the Google Cloud OAuth client:

```text
http://localhost:8000/accounts/google/login/callback/
```

`setup_oauth` creates or updates the database-backed `SocialApp` and links it
to the Site. The database `SocialApp` is the single provider credential
source; environment credentials are setup inputs, not a second OAuth app.

## Separate frontend and backend hosts

For unrelated domains, use the authorization-code exchange:

```text
GET  /api/auth/callback
POST /api/auth/exchange
GET  /api/me with Authorization: Bearer <access-token>
POST /api/auth/token/revoke
```

The redirect carries a five-minute, single-use code in the URL fragment. It
does not carry the reusable access token. The frontend exchanges the code over
HTTPS and keeps the returned token in memory.
