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

# Modular application and middleware lists for unpacking into settings.py
AUTH_APPS = [
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
]

AUTH_MIDDLEWARE = [
    "allauth.account.middleware.AccountMiddleware",
    f"{AUTHENTICATION_PACKAGE}.middleware.BearerTokenMiddleware",
]

CORS_MIDDLEWARE = "corsheaders.middleware.CorsMiddleware"


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


def get_setting(name: str, default: Any = None) -> Any:
    """Resolve an authentication setting from django.conf.settings or default.

    Checks in order:
    1. settings.DJANGO_AUTH dictionary (e.g. settings.DJANGO_AUTH["MODE"])
    2. settings.DJANGO_AUTH_{name} (e.g. settings.DJANGO_AUTH_MODE)
    3. settings.{name} (e.g. settings.ACCOUNT_EMAIL_VERIFICATION)
    4. default value
    """
    try:
        from django.conf import settings

        if not settings.configured:
            return default
    except ImportError:
        return default

    auth_dict = getattr(settings, "DJANGO_AUTH", None)
    if isinstance(auth_dict, dict) and name in auth_dict:
        return auth_dict[name]

    attr_prefixed = f"DJANGO_AUTH_{name}"
    if hasattr(settings, attr_prefixed):
        return getattr(settings, attr_prefixed)

    if hasattr(settings, name):
        return getattr(settings, name)

    return default


def build(
    env: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build all authentication settings from an environment or config mapping.

    Args:
        env: Optional environment mapping. If None and config is None, uses
             os.environ after loading the project's .env file.
        config: Optional DJANGO_AUTH configuration dictionary. Takes precedence
                over environment variables when keys overlap.

    Returns:
        Dictionary of Django settings ready to use.
    """
    if config is None and env is not None:
        # Check if caller passed a DJANGO_AUTH dict as the first positional argument
        known_config_keys = {
            "FRONTEND_URL",
            "MODE",
            "PROVIDERS",
            "EMAIL_VERIFICATION",
            "EMAIL_AUTO_CONNECT",
            "USER_SERIALIZER",
            "ACCESS_TOKEN_LIFETIME_SECONDS",
        }
        if any(k in env for k in known_config_keys):
            config = env
            env = None

    if env is None:
        load_env_file()
        env = dict(os.environ)

    if config and "FRONTEND_URL" in config:
        frontend_url = str(config["FRONTEND_URL"]).rstrip("/")
    else:
        frontend_url = env_str("DJANGO_FRONTEND_URL", "", env).rstrip("/")

    if config and "MODE" in config:
        auth_mode = str(config["MODE"]).strip().lower()
    else:
        auth_mode = env_str("DJANGO_AUTH_MODE", "session", env).strip().lower()
    if auth_mode not in {"session", "cross-domain"}:
        raise ValueError("DJANGO_AUTH_MODE must be session or cross-domain")

    if config and "ACCESS_TOKEN_LIFETIME_SECONDS" in config:
        access_token_lifetime = int(config["ACCESS_TOKEN_LIFETIME_SECONDS"])
    else:
        access_token_lifetime = env_int("DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS", 3600, env)
    if access_token_lifetime < 60:
        raise ValueError("DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS must be at least 60")

    if config and "EMAIL_VERIFICATION" in config:
        email_verification = str(config["EMAIL_VERIFICATION"]).strip().lower()
    else:
        email_verification = env_str(
            "DJANGO_ACCOUNT_EMAIL_VERIFICATION", "mandatory", env
        ).strip().lower()
    if email_verification not in {"mandatory", "optional", "none"}:
        raise ValueError("EMAIL_VERIFICATION must be 'mandatory', 'optional', or 'none'")

    if config and "EMAIL_AUTO_CONNECT" in config:
        email_auto_connect = bool(config["EMAIL_AUTO_CONNECT"])
    else:
        email_auto_connect = env_bool(
            "DJANGO_SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT",
            default=False,
            env=env,
        )

    user_serializer = None
    if config and "USER_SERIALIZER" in config:
        user_serializer = config["USER_SERIALIZER"]
    else:
        val = env_str("DJANGO_AUTH_USER_SERIALIZER", "", env).strip()
        if val:
            user_serializer = val

    if config and "SESSION_COOKIE_DOMAIN" in config:
        session_cookie_domain = config["SESSION_COOKIE_DOMAIN"] or None
    else:
        session_cookie_domain = env_str("DJANGO_SESSION_COOKIE_DOMAIN", "", env) or None

    if config and "SESSION_COOKIE_SAMESITE" in config:
        session_cookie_samesite = str(config["SESSION_COOKIE_SAMESITE"]).strip()
    else:
        session_cookie_samesite = env_str(
            "DJANGO_SESSION_COOKIE_SAMESITE", "Lax", env
        ).strip()

    if config and "CSRF_COOKIE_SAMESITE" in config:
        csrf_cookie_samesite = str(config["CSRF_COOKIE_SAMESITE"]).strip()
    else:
        csrf_cookie_samesite = env_str(
            "DJANGO_CSRF_COOKIE_SAMESITE", "Lax", env
        ).strip()

    valid_samesite_values = {"Strict", "Lax", "None"}
    if session_cookie_samesite not in valid_samesite_values:
        raise ValueError("DJANGO_SESSION_COOKIE_SAMESITE must be Strict, Lax, or None")
    if csrf_cookie_samesite not in valid_samesite_values:
        raise ValueError("DJANGO_CSRF_COOKIE_SAMESITE must be Strict, Lax, or None")

    if config and "SESSION_COOKIE_SECURE" in config:
        session_cookie_secure = bool(config["SESSION_COOKIE_SECURE"])
    else:
        session_cookie_secure = env_bool("DJANGO_SESSION_COOKIE_SECURE", env=env)

    if config and "CSRF_COOKIE_SECURE" in config:
        csrf_cookie_secure = bool(config["CSRF_COOKIE_SECURE"])
    else:
        csrf_cookie_secure = env_bool("DJANGO_CSRF_COOKIE_SECURE", env=env)

    if session_cookie_samesite == "None" and not session_cookie_secure:
        raise ValueError(
            "DJANGO_SESSION_COOKIE_SECURE must be true when session SameSite is None"
        )
    if csrf_cookie_samesite == "None" and not csrf_cookie_secure:
        raise ValueError(
            "DJANGO_CSRF_COOKIE_SECURE must be true when CSRF SameSite is None"
        )

    # Parse enabled providers
    if config and "PROVIDERS" in config:
        raw_providers = config["PROVIDERS"]
        if isinstance(raw_providers, str):
            enabled_providers = [p.strip().lower() for p in raw_providers.split(",") if p.strip()]
        elif isinstance(raw_providers, (list, tuple, set)):
            enabled_providers = [str(p).strip().lower() for p in raw_providers if str(p).strip()]
        else:
            raise ValueError(
                "DJANGO_AUTH['PROVIDERS'] must be a list of provider names or comma-separated string"
            )
    else:
        providers_str = env_str("DJANGO_AUTH_PROVIDERS", "google", env)
        enabled_providers = [p.strip().lower() for p in providers_str.split(",") if p.strip()]

    # Build SOCIALACCOUNT_PROVIDERS dynamically
    socialaccount_providers = {}
    for provider in enabled_providers:
        if provider not in PROVIDER_CONFIGS:
            continue
        cfg = PROVIDER_CONFIGS[provider]
        socialaccount_providers[provider] = {
            "SCOPE": cfg["scope"],
            "AUTH_PARAMS": cfg["auth_params"],
        }

    if config and "CORS_ALLOWED_ORIGINS" in config:
        raw_cors = config["CORS_ALLOWED_ORIGINS"]
        cors_allowed_origins = list(raw_cors) if isinstance(raw_cors, (list, tuple, set)) else [str(raw_cors)]
    else:
        cors_allowed_origins = env_list("DJANGO_CORS_ALLOWED_ORIGINS", env=env)

    if config and "CSRF_TRUSTED_ORIGINS" in config:
        raw_csrf = config["CSRF_TRUSTED_ORIGINS"]
        csrf_trusted_origins = list(raw_csrf) if isinstance(raw_csrf, (list, tuple, set)) else [str(raw_csrf)]
    else:
        csrf_trusted_origins = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", env=env)

    if config and "SIGNUP_FIELDS" in config:
        signup_fields = config["SIGNUP_FIELDS"]
    elif email_verification == "mandatory":
        signup_fields = ["email*", "username*", "password1*"]
    else:
        signup_fields = ["email", "username*", "password1*"]

    result = {
        "AUTH_APPS": AUTH_APPS,
        "AUTH_MIDDLEWARE": AUTH_MIDDLEWARE,
        "CORS_MIDDLEWARE": CORS_MIDDLEWARE,
        "AUTHENTICATION_BACKENDS": [
            "django.contrib.auth.backends.ModelBackend",
            "allauth.account.auth_backends.AuthenticationBackend",
        ],
        "SOCIALACCOUNT_ADAPTER": (
            f"{AUTHENTICATION_PACKAGE}.adapters.AuthenticationSocialAccountAdapter"
        ),
        "SITE_ID": 1,
        "HEADLESS_ONLY": True,
        "DJANGO_AUTH_MODE": auth_mode,
        "DJANGO_AUTH_FRONTEND_URL": frontend_url,
        "DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS": access_token_lifetime,
        "ACCOUNT_EMAIL_VERIFICATION": email_verification,
        "ACCOUNT_SIGNUP_FIELDS": signup_fields,
        "SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT": email_auto_connect,
        "HEADLESS_FRONTEND_URLS": {
            "account_confirm_email": f"{frontend_url}/account/confirm-email/{{key}}",
            "account_reset_password": f"{frontend_url}/account/password/reset",
            "account_reset_password_from_key": (
                f"{frontend_url}/account/password/reset/key/{{key}}"
            ),
            "account_signup": f"{frontend_url}/account/signup",
            "socialaccount_login_error": f"{frontend_url}/account/social/login/error",
        },
        "CORS_ALLOWED_ORIGINS": cors_allowed_origins,
        "CORS_ALLOW_CREDENTIALS": True,
        "CSRF_TRUSTED_ORIGINS": csrf_trusted_origins,
        "SESSION_COOKIE_SECURE": session_cookie_secure,
        "CSRF_COOKIE_SECURE": csrf_cookie_secure,
        "SESSION_COOKIE_DOMAIN": session_cookie_domain,
        "SESSION_COOKIE_HTTPONLY": True,
        "CSRF_COOKIE_HTTPONLY": False,
        "SESSION_COOKIE_SAMESITE": session_cookie_samesite,
        "CSRF_COOKIE_SAMESITE": csrf_cookie_samesite,
        "SOCIALACCOUNT_PROVIDERS": socialaccount_providers,
    }
    if user_serializer is not None:
        result["DJANGO_AUTH_USER_SERIALIZER"] = user_serializer
    return result


# Load .env and build the actual exported settings
load_env_file()
_settings = build()

# Export auth-specific configuration (developers unpack *AUTH_APPS and *AUTH_MIDDLEWARE)
AUTHENTICATION_BACKENDS = _settings["AUTHENTICATION_BACKENDS"]
SOCIALACCOUNT_ADAPTER = _settings["SOCIALACCOUNT_ADAPTER"]
SITE_ID = _settings["SITE_ID"]
HEADLESS_ONLY = _settings["HEADLESS_ONLY"]
DJANGO_AUTH_MODE = _settings["DJANGO_AUTH_MODE"]
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
SOCIALACCOUNT_PROVIDERS = _settings["SOCIALACCOUNT_PROVIDERS"]
DJANGO_AUTH_FRONTEND_URL = _settings["DJANGO_AUTH_FRONTEND_URL"]
DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS = _settings[
    "DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS"
]
ACCOUNT_EMAIL_VERIFICATION = _settings["ACCOUNT_EMAIL_VERIFICATION"]
ACCOUNT_SIGNUP_FIELDS = _settings["ACCOUNT_SIGNUP_FIELDS"]
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = _settings[

    "SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT"
]
DJANGO_AUTH_USER_SERIALIZER = _settings.get("DJANGO_AUTH_USER_SERIALIZER", None)
