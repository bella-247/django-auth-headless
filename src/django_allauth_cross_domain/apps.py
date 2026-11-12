"""Django app configuration for the authentication module."""

from django.apps import AppConfig
from django.core.checks import Error, Tags, Warning as CheckWarning, register


@register(Tags.security)
def check_auth_configuration(app_configs, **kwargs):
    """Validate authentication configuration without mutating settings."""
    from django.conf import settings
    from .conf import get_setting

    errors = []
    if not settings.configured:
        return errors

    backends = getattr(settings, "AUTHENTICATION_BACKENDS", [])
    allauth_backend = "allauth.account.auth_backends.AuthenticationBackend"
    if allauth_backend not in backends:
        errors.append(
            CheckWarning(
                f"{allauth_backend!r} is not in AUTHENTICATION_BACKENDS.",
                hint="Add it to settings.AUTHENTICATION_BACKENDS for django-allauth to authenticate users.",
                id="django_allauth_cross_domain.W001",
            )
        )

    mode = get_setting("MODE", getattr(settings, "DJANGO_AUTH_MODE", "session"))
    if mode == "cross-domain":
        frontend_url = get_setting(
            "FRONTEND_URL", getattr(settings, "DJANGO_AUTH_FRONTEND_URL", "")
        )
        if not frontend_url:
            errors.append(
                Error(
                    "DJANGO_AUTH['FRONTEND_URL'] is required when MODE is 'cross-domain'.",
                    hint="Set FRONTEND_URL in DJANGO_AUTH or DJANGO_FRONTEND_URL in environment.",
                    id="django_allauth_cross_domain.E001",
                )
            )

    return errors


class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = __package__
    verbose_name = "Allauth Cross Domain"

    def ready(self) -> None:
        from .signals import register_signals

        register_signals()
