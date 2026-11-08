"""Django app configuration for the authentication module."""

from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = __package__
    verbose_name = "Authentication"

    def ready(self) -> None:
        try:
            from django.conf import settings
        except ImportError:
            return

        if not settings.configured:
            return

        user_config = getattr(settings, "DJANGO_AUTH", None)
        if isinstance(user_config, dict):
            from .conf import build

            auth_settings = build(config=user_config)

            derived_keys = set()
            derived_map = {
                "FRONTEND_URL": ["DJANGO_AUTH_FRONTEND_URL", "HEADLESS_FRONTEND_URLS"],
                "MODE": ["DJANGO_AUTH_MODE"],
                "ACCESS_TOKEN_LIFETIME_SECONDS": ["DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS"],
                "PROVIDERS": ["SOCIALACCOUNT_PROVIDERS"],
                "EMAIL_VERIFICATION": ["ACCOUNT_EMAIL_VERIFICATION", "ACCOUNT_SIGNUP_FIELDS"],
                "EMAIL_AUTO_CONNECT": ["SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT"],
                "USER_SERIALIZER": ["DJANGO_AUTH_USER_SERIALIZER"],
                "CORS_ALLOWED_ORIGINS": ["CORS_ALLOWED_ORIGINS"],
                "CSRF_TRUSTED_ORIGINS": ["CSRF_TRUSTED_ORIGINS"],
                "SESSION_COOKIE_DOMAIN": ["SESSION_COOKIE_DOMAIN"],
                "SESSION_COOKIE_SECURE": ["SESSION_COOKIE_SECURE"],
                "CSRF_COOKIE_SECURE": ["CSRF_COOKIE_SECURE"],
                "SESSION_COOKIE_SAMESITE": ["SESSION_COOKIE_SAMESITE"],
                "CSRF_COOKIE_SAMESITE": ["CSRF_COOKIE_SAMESITE"],
            }
            for cfg_key in user_config:
                derived_keys.update(derived_map.get(cfg_key, []))

            for key, value in auth_settings.items():
                if key in derived_keys or not hasattr(settings, key):
                    setattr(settings, key, value)
                elif key == "AUTHENTICATION_BACKENDS":
                    backends = list(getattr(settings, key))
                    allauth_backend = "allauth.account.auth_backends.AuthenticationBackend"
                    if allauth_backend not in backends:
                        backends.append(allauth_backend)
                        setattr(settings, key, backends)
