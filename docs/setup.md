# Setup guide

This guide configures `django-auth-headless` in an existing Django project.

## Install and configure

```bash
pip install django-auth-headless
# or
uv add django-auth-headless
```

In `settings.py`, unpack the modular app and middleware lists so you retain full control over your project's custom apps (e.g. `users.CustomUser`) and middleware ordering:

```python
from django_auth_headless.conf import (
    AUTH_APPS,
    AUTH_MIDDLEWARE,
    CORS_MIDDLEWARE,
    AUTHENTICATION_BACKENDS,
    SOCIALACCOUNT_ADAPTER,
    SOCIALACCOUNT_PROVIDERS,
    HEADLESS_ONLY,
    HEADLESS_FRONTEND_URLS,
    DJANGO_AUTH_MODE,
    DJANGO_AUTH_FRONTEND_URL,
    DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS,
    CORS_ALLOWED_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    CSRF_TRUSTED_ORIGINS,
    SESSION_COOKIE_SECURE,
    CSRF_COOKIE_SECURE,
    SESSION_COOKIE_DOMAIN,
    SESSION_COOKIE_HTTPONLY,
    CSRF_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,
    CSRF_COOKIE_SAMESITE,
    SITE_ID,
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Add your own apps (e.g., custom user model app):
    # "users",
    "corsheaders",
    *AUTH_APPS,
]

MIDDLEWARE = [
    CORS_MIDDLEWARE,  # Placed at the top for CORS handling
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    *AUTH_MIDDLEWARE,  # Injects allauth AccountMiddleware & BearerTokenMiddleware
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

### Custom User Models

The package automatically adapts to any `AUTH_USER_MODEL`, including models with:
- No `username` field (`USERNAME_FIELD = "email"`).
- Custom email field names (via `get_email_field_name()`).
- No email field (e.g., phone-number-only authentication).

#### Custom User Serializer Hook

If you want `/api/me` to return additional custom profile fields (like `role`, `avatar`, or `company`), define a serializer function in your project:

```python
# in users/serializers.py
from django_auth_headless.serializers import default_user_serializer

def custom_user_serializer(user):
    data = default_user_serializer(user)
    data["role"] = getattr(user, "role", "member")
    data["avatar"] = getattr(user, "avatar_url", "")
    return data
```

And point `DJANGO_AUTH_USER_SERIALIZER` to it in `settings.py`:

```python
DJANGO_AUTH_USER_SERIALIZER = "users.serializers.custom_user_serializer"
```

Include the URLs:

```python
from django_auth_headless.urls import urlpatterns as auth_urlpatterns

urlpatterns = [*auth_urlpatterns]
```

Create `.env` beside `manage.py`:

```dotenv
DJANGO_FRONTEND_URL=http://localhost:5173
DJANGO_AUTH_MODE=session
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

For unrelated domains, set `DJANGO_AUTH_MODE=cross-domain` and use the
authorization-code exchange:

```text
GET  /api/auth/callback
POST /api/auth/exchange
GET  /api/me with Authorization: Bearer <access-token>
POST /api/auth/token/revoke
```

The redirect carries a five-minute, single-use code in the URL fragment. It
does not carry the reusable access token. The frontend exchanges the code over
HTTPS and keeps the returned token in memory.

For same-site deployments, keep `DJANGO_AUTH_MODE=session`. The normal Django
session cookie remains the authentication mechanism, and the token callback,
exchange, and revocation endpoints are disabled.
