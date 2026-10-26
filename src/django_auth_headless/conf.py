"""Authentication configuration loaded from environment variables.

This is the ONLY file in the authentication package that reads environment
variables or loads .env files. All other modules import finished values from
here or from the pure build() function.

The build() function accepts an explicit mapping so tests can pass fake
environments without mutating os.environ.
"""

import os
from typing import Any, Mapping

from .utils import (
    env_bool,
    env_int,
    env_list,
    env_str,
    load_env_file,
)

AUTHENTICATION_PACKAGE = __package__


# Provider configurations - defines required env vars per provider
PROVIDER_CONFIGS = {
    "google": {
        "client_id_env": "DJANGO_GOOGLE_CLIENT_ID",
        "client_secret_env": "DJANGO_GOOGLE_CLIENT_SECRET",
        "scope": ["profile", "email"],
        "auth_params": {"access_type": "online"},
    },
    "github": {
        "client_id_env": "DJANGO_GITHUB_CLIENT_ID",
        "client_secret_env": "DJANGO_GITHUB_CLIENT_SECRET",
        "scope": ["user:email", "read:user"],
        "auth_params": {},
    },
    "gitlab": {
        "client_id_env": "DJANGO_GITLAB_CLIENT_ID",
        "client_secret_env": "DJANGO_GITLAB_CLIENT_SECRET",
        "scope": ["read_user", "email"],
        "auth_params": {},
    },
    "microsoft": {
        "client_id_env": "DJANGO_MICROSOFT_CLIENT_ID",
        "client_secret_env": "DJANGO_MICROSOFT_CLIENT_SECRET",
        "scope": ["User.Read", "email"],
        "auth_params": {},
    },
}


def build(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build all authentication settings from an environment mapping.

    Args:
        env: Optional environment mapping. If None, uses os.environ after
             loading the project's .env file.

    Returns:
        Dictionary of Django settings ready to use.
    """
    if env is None:
        load_env_file()
        env = dict(os.environ)

    frontend_url = env_str("DJANGO_FRONTEND_URL", "", env).rstrip("/")
    access_token_lifetime = env_int("DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS", 3600, env)
    if access_token_lifetime < 60:
        raise ValueError("DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS must be at least 60")
    session_cookie_domain = env_str("DJANGO_SESSION_COOKIE_DOMAIN", "", env) or None
    session_cookie_samesite = env_str(
        "DJANGO_SESSION_COOKIE_SAMESITE", "Lax", env
    ).strip()
    csrf_cookie_samesite = env_str(
        "DJANGO_CSRF_COOKIE_SAMESITE", "Lax", env
    ).strip()
    valid_samesite_values = {"Strict", "Lax", "None"}
    if session_cookie_samesite not in valid_samesite_values:
        raise ValueError("DJANGO_SESSION_COOKIE_SAMESITE must be Strict, Lax, or None")
    if csrf_cookie_samesite not in valid_samesite_values:
        raise ValueError("DJANGO_CSRF_COOKIE_SAMESITE must be Strict, Lax, or None")
    session_cookie_secure = env_bool("DJANGO_SESSION_COOKIE_SECURE", env=env)
    csrf_cookie_secure = env_bool("DJANGO_CSRF_COOKIE_SECURE", env=env)
    if session_cookie_samesite == "None" and not session_cookie_secure:
        raise ValueError(
            "DJANGO_SESSION_COOKIE_SECURE must be true when session SameSite is None"
        )
    if csrf_cookie_samesite == "None" and not csrf_cookie_secure:
        raise ValueError(
            "DJANGO_CSRF_COOKIE_SECURE must be true when CSRF SameSite is None"
        )

    # Parse enabled providers from DJANGO_AUTH_PROVIDERS (comma-separated, default "google")
    providers_str = env_str("DJANGO_AUTH_PROVIDERS", "google", env)
    enabled_providers = [p.strip().lower() for p in providers_str.split(",") if p.strip()]

    # Build SOCIALACCOUNT_PROVIDERS dynamically
    socialaccount_providers = {}
    for provider in enabled_providers:
        if provider not in PROVIDER_CONFIGS:
            continue
        config = PROVIDER_CONFIGS[provider]
        socialaccount_providers[provider] = {
            "SCOPE": config["scope"],
            "AUTH_PARAMS": config["auth_params"],
        }

    return {
        "INSTALLED_APPS": [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "django.contrib.sites",
            "allauth",
            "allauth.account",
            "allauth.socialaccount",
            "allauth.socialaccount.providers.google",
            "allauth.socialaccount.providers.github",
            "allauth.socialaccount.providers.gitlab",
            "allauth.socialaccount.providers.microsoft",
            "allauth.headless",
            "corsheaders",
            AUTHENTICATION_PACKAGE,
        ],
        "MIDDLEWARE": [
            "corsheaders.middleware.CorsMiddleware",
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "allauth.account.middleware.AccountMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ],
        "AUTHENTICATION_BACKENDS": [
            "django.contrib.auth.backends.ModelBackend",
            "allauth.account.auth_backends.AuthenticationBackend",
        ],
        "SOCIALACCOUNT_ADAPTER": (
            f"{AUTHENTICATION_PACKAGE}.adapters.AuthenticationSocialAccountAdapter"
        ),
        "SITE_ID": 1,
        "HEADLESS_ONLY": True,
        "DJANGO_AUTH_FRONTEND_URL": frontend_url,
        "DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS": access_token_lifetime,
        "HEADLESS_FRONTEND_URLS": {
            "account_confirm_email": f"{frontend_url}/account/confirm-email/{{key}}",
            "account_reset_password": f"{frontend_url}/account/password/reset",
            "account_reset_password_from_key": (
                f"{frontend_url}/account/password/reset/key/{{key}}"
            ),
            "account_signup": f"{frontend_url}/account/signup",
            "socialaccount_login_error": f"{frontend_url}/account/social/login/error",
        },
        "CORS_ALLOWED_ORIGINS": env_list("DJANGO_CORS_ALLOWED_ORIGINS", env=env),
        "CORS_ALLOW_CREDENTIALS": True,
        "CSRF_TRUSTED_ORIGINS": env_list("DJANGO_CSRF_TRUSTED_ORIGINS", env=env),
        "SESSION_COOKIE_SECURE": session_cookie_secure,
        "CSRF_COOKIE_SECURE": csrf_cookie_secure,
        "SESSION_COOKIE_DOMAIN": session_cookie_domain,
        "SESSION_COOKIE_HTTPONLY": True,
        "CSRF_COOKIE_HTTPONLY": False,
        "SESSION_COOKIE_SAMESITE": session_cookie_samesite,
        "CSRF_COOKIE_SAMESITE": csrf_cookie_samesite,
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_REFERRER_POLICY": "no-referrer",
        "SECURE_SSL_REDIRECT": env_bool("DJANGO_SECURE_SSL_REDIRECT", env=env),
        "SECURE_HSTS_SECONDS": env_int("DJANGO_SECURE_HSTS_SECONDS", env=env),
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": env_bool(
            "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", env=env
        ),
        "SECURE_HSTS_PRELOAD": env_bool("DJANGO_SECURE_HSTS_PRELOAD", env=env),
        "SOCIALACCOUNT_PROVIDERS": socialaccount_providers,
    }


# Load .env and build the actual exported settings
load_env_file()
_settings = build()

# Export everything so `from .conf import *` works
INSTALLED_APPS = _settings["INSTALLED_APPS"]
MIDDLEWARE = _settings["MIDDLEWARE"]
AUTHENTICATION_BACKENDS = _settings["AUTHENTICATION_BACKENDS"]
SOCIALACCOUNT_ADAPTER = _settings["SOCIALACCOUNT_ADAPTER"]
SITE_ID = _settings["SITE_ID"]
HEADLESS_ONLY = _settings["HEADLESS_ONLY"]
HEADLESS_FRONTEND_URLS = _settings["HEADLESS_FRONTEND_URLS"]
CORS_ALLOWED_ORIGINS = _settings["CORS_ALLOWED_ORIGINS"]
CORS_ALLOW_CREDENTIALS = _settings["CORS_ALLOW_CREDENTIALS"]
CSRF_TRUSTED_ORIGINS = _settings["CSRF_TRUSTED_ORIGINS"]
SESSION_COOKIE_SECURE = _settings["SESSION_COOKIE_SECURE"]
CSRF_COOKIE_SECURE = _settings["CSRF_COOKIE_SECURE"]
SESSION_COOKIE_DOMAIN = _settings["SESSION_COOKIE_DOMAIN"]
SESSION_COOKIE_HTTPONLY = _settings["SESSION_COOKIE_HTTPONLY"]
CSRF_COOKIE_HTTPONLY = _settings["CSRF_COOKIE_HTTPONLY"]
SESSION_COOKIE_SAMESITE = _settings["SESSION_COOKIE_SAMESITE"]
CSRF_COOKIE_SAMESITE = _settings["CSRF_COOKIE_SAMESITE"]
SECURE_CONTENT_TYPE_NOSNIFF = _settings["SECURE_CONTENT_TYPE_NOSNIFF"]
SECURE_REFERRER_POLICY = _settings["SECURE_REFERRER_POLICY"]
SECURE_SSL_REDIRECT = _settings["SECURE_SSL_REDIRECT"]
SECURE_HSTS_SECONDS = _settings["SECURE_HSTS_SECONDS"]
SECURE_HSTS_INCLUDE_SUBDOMAINS = _settings["SECURE_HSTS_INCLUDE_SUBDOMAINS"]
SECURE_HSTS_PRELOAD = _settings["SECURE_HSTS_PRELOAD"]
SOCIALACCOUNT_PROVIDERS = _settings["SOCIALACCOUNT_PROVIDERS"]
DJANGO_AUTH_FRONTEND_URL = _settings["DJANGO_AUTH_FRONTEND_URL"]
DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS = _settings[
    "DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS"
]