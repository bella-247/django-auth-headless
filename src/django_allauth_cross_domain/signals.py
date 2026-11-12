"""Signal handlers for automatic token revocation and lifecycle management."""

import logging

from django.conf import settings
from django.db.models.signals import post_save, pre_save

from .models import revoke_all_tokens_for_user

logger = logging.getLogger("django_allauth_cross_domain")


def on_password_change(sender, request=None, user=None, **kwargs):
    """Revoke all active tokens when a user's password changes via allauth."""
    target_user = user or kwargs.get("user")
    if target_user:
        logger.info(
            "Revoking all active tokens for user_id=%s following allauth password change",
            target_user.pk,
        )
        revoke_all_tokens_for_user(target_user)


def on_user_pre_save(sender, instance, **kwargs):
    """Detect password hash changes prior to save (e.g. Django Admin or set_password)."""
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values("password").first()
            if old and old["password"] != instance.password:
                instance._password_has_changed = True
        except Exception:
            pass


def on_user_saved(sender, instance, **kwargs):
    """Revoke all active tokens if user account is deactivated or password modified."""
    if not getattr(instance, "is_active", True) or getattr(instance, "_password_has_changed", False):
        logger.info(
            "Revoking all active tokens for user_id=%s following deactivation or password change",
            instance.pk,
        )
        revoke_all_tokens_for_user(instance)


def register_signals():
    """Register all lifecycle signal receivers."""
    try:
        from allauth.account.signals import (
            password_changed,
            password_reset,
            password_set,
        )

        password_changed.connect(
            on_password_change,
            dispatch_uid="django_allauth_cross_domain_password_changed",
        )
        password_reset.connect(
            on_password_change,
            dispatch_uid="django_allauth_cross_domain_password_reset",
        )
        password_set.connect(
            on_password_change,
            dispatch_uid="django_allauth_cross_domain_password_set",
        )
    except ImportError:
        pass

    user_model = getattr(settings, "AUTH_USER_MODEL", "auth.User")
    pre_save.connect(
        on_user_pre_save,
        sender=user_model,
        dispatch_uid="django_allauth_cross_domain_user_pre_save",
    )
    post_save.connect(
        on_user_saved,
        sender=user_model,
        dispatch_uid="django_allauth_cross_domain_user_saved",
    )
