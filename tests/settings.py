SECRET_KEY = "test-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["testserver", "localhost"]
ROOT_URLCONF = "tests.urls"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

from django_auth_headless.conf import (  # noqa: E402
    AUTHENTICATION_BACKENDS,
    DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS,
    DJANGO_AUTH_FRONTEND_URL,
    INSTALLED_APPS,
    SOCIALACCOUNT_ADAPTER,
    SOCIALACCOUNT_PROVIDERS,
)

INSTALLED_APPS = [*INSTALLED_APPS]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]
AUTHENTICATION_BACKENDS = AUTHENTICATION_BACKENDS
DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS = DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS
DJANGO_AUTH_FRONTEND_URL = DJANGO_AUTH_FRONTEND_URL
SOCIALACCOUNT_ADAPTER = SOCIALACCOUNT_ADAPTER
SOCIALACCOUNT_PROVIDERS = SOCIALACCOUNT_PROVIDERS
SITE_ID = 1
HEADLESS_ONLY = True
DJANGO_AUTH_FRONTEND_URL = "http://localhost:5173"
DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS = 3600
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
