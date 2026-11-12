# Setup guide

This guide configures `django-allauth-cross-domain` in an existing Django project.

## Install and configure

```bash
pip install django-allauth-cross-domain
# or
uv add django-allauth-cross-domain
```

In `settings.py`, unpack the modular app and middleware lists, and define the `DJANGO_AUTH` dictionary:

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
    # "USER_SERIALIZER": "users.serializers.custom_user_serializer",
}
```

> **Note:** If you prefer environment variables (`.env`) or importing individual constants, you can also import `from django_allauth_cross_domain.conf import *` or individual settings like `ACCOUNT_EMAIL_VERIFICATION`, `SOCIALACCOUNT_PROVIDERS`, etc.

### Security Controls

- **`EMAIL_VERIFICATION`**: Defaults to `"mandatory"`. Ensures new signups verify their email address before logging in or completing headless authentication flows. Can also be set to `"optional"` or `"none"`.
- **`EMAIL_AUTO_CONNECT`**: Defaults to `False`. Prevents OAuth pre-hijacking attacks where a malicious actor could register a third-party social account with a victim's email and silently link it to an existing unverified local account.


### Custom User Models

The package automatically adapts to any `AUTH_USER_MODEL`, including models with:
- No `username` field (`USERNAME_FIELD = "email"`).
- Custom email field names (via `get_email_field_name()`).
- No email field (e.g., phone-number-only authentication).

#### Custom User Serializer Hook

If you want `/api/me` to return additional custom profile fields (like `role`, `avatar`, or `company`), define a serializer function in your project:

```python
# in users/serializers.py
from django_allauth_cross_domain.serializers import default_user_serializer

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

### Framework Integration (DRF & Django Ninja)

#### Django REST Framework (DRF)
To authenticate API requests in DRF without triggering CSRF failures on mutating requests (POST/PUT/DELETE):

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "django_allauth_cross_domain.contrib.rest_framework.BearerTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}
```

#### Django Ninja
To protect Django Ninja endpoints with Bearer tokens:

```python
from ninja import NinjaAPI
from django_allauth_cross_domain.contrib.ninja import BearerAuth

api = NinjaAPI(auth=BearerAuth())

@api.get("/protected")
def protected_view(request):
    return {"user": request.auth.username}
```

Include the URLs:

```python
from django_allauth_cross_domain.urls import urlpatterns as auth_urlpatterns

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

## Maintenance & Token Cleanup

Expired access tokens, refresh tokens, and redeemed handoff codes can be cleaned up periodically using the built-in management command:

```bash
# Purge all expired records immediately:
python manage.py cleanup_tokens

# Or keep expired records for 7 days before purging:
python manage.py cleanup_tokens --days 7
```

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
