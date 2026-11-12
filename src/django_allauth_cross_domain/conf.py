"""Authentication configuration loaded from environment variables and settings.

This is the central configuration module for django-allauth-cross-domain.
Settings can be defined in Django's `settings.py` via `DJANGO_AUTH = { ... }`,
via individual `DJANGO_AUTH_*` settings, or loaded from environment variables.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from .utils import (
    env_bool,
    env_int,
    env_list,
    env_str,
    load_env_file,
    to_bool,
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
    "allauth.socialaccount.providers.apple",
    "allauth.headless",
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
    "apple": {
        "client_id_env": "DJANGO_APPLE_CLIENT_ID",
        "client_secret_env": "DJANGO_APPLE_CLIENT_SECRET",
        "scope": ["name", "email"],
        "auth_params": {},
    },
}

KNOWN_CONFIG_KEYS = {
    "FRONTEND_URL",
    "MODE",
    "PROVIDERS",
    "EMAIL_VERIFICATION",
    "EMAIL_AUTO_CONNECT",
    "ENFORCE_PKCE",
    "HANDOFF_CODE_LIFETIME_SECONDS",
    "TRUST_PROXY_HEADERS",
    "USER_SERIALIZER",
    "ACCESS_TOKEN_LIFETIME_SECONDS",
    "REFRESH_TOKEN_LIFETIME_SECONDS",
    "ROTATE_REFRESH_TOKENS",
    "SESSION_COOKIE_DOMAIN",
    "SESSION_COOKIE_SAMESITE",
    "CSRF_COOKIE_SAMESITE",
    "SESSION_COOKIE_SECURE",
    "CSRF_COOKIE_SECURE",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "SIGNUP_FIELDS",
}


def _coerce_setting(name: str, value: Any) -> Any:
    """Coerce string/environment values into expected Python types."""
    if value is None:
        return None
    if name in {
        "ACCESS_TOKEN_LIFETIME_SECONDS",
        "REFRESH_TOKEN_LIFETIME_SECONDS",
        "HANDOFF_CODE_LIFETIME_SECONDS",
    }:
        return int(value)
    if name in {
        "ROTATE_REFRESH_TOKENS",
        "ENFORCE_PKCE",
        "EMAIL_AUTO_CONNECT",
        "TRUST_PROXY_HEADERS",
        "SESSION_COOKIE_SECURE",
        "CSRF_COOKIE_SECURE",
    }:
        return to_bool(value)
    if name == "MODE":
        return str(value).strip().lower()
    if name == "FRONTEND_URL":
        return str(value).strip().rstrip("/")
    return value


def get_setting(name: str, default: Any = None) -> Any:
    """Resolve an authentication setting with fallback and type coercion.

    Checks in order:
    1. settings.DJANGO_AUTH dictionary (e.g. settings.DJANGO_AUTH["MODE"])
    2. settings.DJANGO_AUTH_{name} (e.g. settings.DJANGO_AUTH_MODE)
    3. os.environ["DJANGO_AUTH_{name}"] or os.environ["DJANGO_{name}"]
    4. default value
    """
    raw_val = None
    found = False

    try:
        from django.conf import settings

        if settings.configured:
            auth_dict = getattr(settings, "DJANGO_AUTH", None)
            if isinstance(auth_dict, dict) and name in auth_dict:
                raw_val = auth_dict[name]
                found = True
            else:
                attr_prefixed = f"DJANGO_AUTH_{name}"
                if hasattr(settings, attr_prefixed):
                    raw_val = getattr(settings, attr_prefixed)
                    found = True
    except ImportError:
        pass

    if not found:
        env_auth_key = f"DJANGO_AUTH_{name}"
        env_general_key = f"DJANGO_{name}"
        if env_auth_key in os.environ:
            raw_val = os.environ[env_auth_key]
            found = True
        elif env_general_key in os.environ:
            raw_val = os.environ[env_general_key]
            found = True

    if not found:
        return default

    try:
        return _coerce_setting(name, raw_val)
    except (ValueError, TypeError):
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
        if any(k in env for k in KNOWN_CONFIG_KEYS):
            config = env
            env = None

    if config is not None:
        unknown_keys = set(config.keys()) - KNOWN_CONFIG_KEYS
        if unknown_keys:
            raise ValueError(
                f"Unknown DJANGO_AUTH configuration key(s): {', '.join(sorted(unknown_keys))}"
            )

    if env is None:
        load_env_file()
        env = dict(os.environ)

    if config and "FRONTEND_URL" in config:
        frontend_url = str(config["FRONTEND_URL"]).strip().rstrip("/")
    else:
        frontend_url = env_str("DJANGO_FRONTEND_URL", "", env).strip().rstrip("/")

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

    if config and "REFRESH_TOKEN_LIFETIME_SECONDS" in config:
        refresh_token_lifetime = int(config["REFRESH_TOKEN_LIFETIME_SECONDS"])
    else:
        refresh_token_lifetime = env_int(
            "DJANGO_REFRESH_TOKEN_LIFETIME_SECONDS", 2592000, env
        )
    if refresh_token_lifetime < 60:
        raise ValueError("DJANGO_REFRESH_TOKEN_LIFETIME_SECONDS must be at least 60")

    if config and "ROTATE_REFRESH_TOKENS" in config:
        rotate_refresh_tokens = to_bool(config["ROTATE_REFRESH_TOKENS"])
    else:
        rotate_refresh_tokens = to_bool(
            env.get("DJANGO_AUTH_ROTATE_REFRESH_TOKENS"), default=True
        )

    if config and "ENFORCE_PKCE" in config:
        enforce_pkce = to_bool(config["ENFORCE_PKCE"])
    else:
        enforce_pkce = to_bool(env.get("DJANGO_AUTH_ENFORCE_PKCE"), default=False)

    if config and "HANDOFF_CODE_LIFETIME_SECONDS" in config:
        handoff_code_lifetime = int(config["HANDOFF_CODE_LIFETIME_SECONDS"])
    else:
        handoff_code_lifetime = env_int(
            "DJANGO_AUTH_HANDOFF_CODE_LIFETIME_SECONDS", 60, env
        )
    if handoff_code_lifetime < 1:
        raise ValueError("DJANGO_AUTH_HANDOFF_CODE_LIFETIME_SECONDS must be at least 1")

    if config and "TRUST_PROXY_HEADERS" in config:
        trust_proxy_headers = to_bool(config["TRUST_PROXY_HEADERS"])
    else:
        trust_proxy_headers = to_bool(
            env.get("DJANGO_AUTH_TRUST_PROXY_HEADERS"), default=False
        )

    if config and "EMAIL_VERIFICATION" in config:
        email_verification = str(config["EMAIL_VERIFICATION"]).strip().lower()
    else:
        email_verification = env_str(
            "DJANGO_ACCOUNT_EMAIL_VERIFICATION", "mandatory", env
        ).strip().lower()
    if email_verification not in {"mandatory", "optional", "none"}:
        raise ValueError("EMAIL_VERIFICATION must be 'mandatory', 'optional', or 'none'")

    if config and "EMAIL_AUTO_CONNECT" in config:
        email_auto_connect = to_bool(config["EMAIL_AUTO_CONNECT"])
    else:
        email_auto_connect = to_bool(
            env.get("DJANGO_SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT"),
            default=False,
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
        session_cookie_secure = to_bool(config["SESSION_COOKIE_SECURE"])
    else:
        session_cookie_secure = to_bool(
            env.get("DJANGO_SESSION_COOKIE_SECURE"), default=False
        )

    if config and "CSRF_COOKIE_SECURE" in config:
        csrf_cookie_secure = to_bool(config["CSRF_COOKIE_SECURE"])
    else:
        csrf_cookie_secure = to_bool(
            env.get("DJANGO_CSRF_COOKIE_SECURE"), default=False
        )

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

    # Validate provider names and build SOCIALACCOUNT_PROVIDERS
    socialaccount_providers = {}
    for provider in enabled_providers:
        if provider not in PROVIDER_CONFIGS:
            raise ValueError(
                f"Unsupported OAuth provider: '{provider}'. Supported providers are: {', '.join(sorted(PROVIDER_CONFIGS.keys()))}"
            )
        cfg = PROVIDER_CONFIGS[provider]
        socialaccount_providers[provider] = {
            "SCOPE": cfg["scope"],
            "AUTH_PARAMS": cfg["auth_params"],
        }

    # Split string origins if provided as comma-separated strings
    if config and "CORS_ALLOWED_ORIGINS" in config:
        raw_cors = config["CORS_ALLOWED_ORIGINS"]
        if isinstance(raw_cors, str):
            cors_allowed_origins = [o.strip() for o in raw_cors.split(",") if o.strip()]
        elif isinstance(raw_cors, (list, tuple, set)):
            cors_allowed_origins = [str(o).strip() for o in raw_cors if str(o).strip()]
        else:
            cors_allowed_origins = [str(raw_cors)]
    else:
        cors_allowed_origins = env_list("DJANGO_CORS_ALLOWED_ORIGINS", env=env)

    if config and "CSRF_TRUSTED_ORIGINS" in config:
        raw_csrf = config["CSRF_TRUSTED_ORIGINS"]
        if isinstance(raw_csrf, str):
            csrf_trusted_origins = [o.strip() for o in raw_csrf.split(",") if o.strip()]
        elif isinstance(raw_csrf, (list, tuple, set)):
            csrf_trusted_origins = [str(o).strip() for o in raw_csrf if str(o).strip()]
        else:
            csrf_trusted_origins = [str(raw_csrf)]
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
        "DJANGO_REFRESH_TOKEN_LIFETIME_SECONDS": refresh_token_lifetime,
        "DJANGO_AUTH_ROTATE_REFRESH_TOKENS": rotate_refresh_tokens,
        "DJANGO_AUTH_ENFORCE_PKCE": enforce_pkce,
        "DJANGO_AUTH_HANDOFF_CODE_LIFETIME_SECONDS": handoff_code_lifetime,
        "DJANGO_AUTH_TRUST_PROXY_HEADERS": trust_proxy_headers,
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


def apply_settings(
    target_globals: dict[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    env: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build authentication settings and apply them to target namespace (e.g. globals())."""
    settings_dict = build(env=env, config=config)
    if target_globals is not None:
        target_globals.update(settings_dict)
    return settings_dict


configure_auth = apply_settings

# Module-level static exports
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SOCIALACCOUNT_ADAPTER = (
    f"{AUTHENTICATION_PACKAGE}.adapters.AuthenticationSocialAccountAdapter"
)
SITE_ID = 1
HEADLESS_ONLY = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": PROVIDER_CONFIGS["google"]["scope"],
        "AUTH_PARAMS": PROVIDER_CONFIGS["google"]["auth_params"],
    }
}

__all__ = [
    "AUTH_APPS",
    "AUTH_MIDDLEWARE",
    "CORS_MIDDLEWARE",
    "AUTHENTICATION_BACKENDS",
    "SOCIALACCOUNT_ADAPTER",
    "SITE_ID",
    "HEADLESS_ONLY",
    "ACCOUNT_EMAIL_VERIFICATION",
    "SOCIALACCOUNT_PROVIDERS",
    "PROVIDER_CONFIGS",
    "KNOWN_CONFIG_KEYS",
    "get_setting",
    "build",
    "apply_settings",
    "configure_auth",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve remaining exported settings."""
    auth_val = get_setting(name)
    if auth_val is not None:
        return auth_val
    settings_dict = build()
    if name in settings_dict:
        return settings_dict[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
