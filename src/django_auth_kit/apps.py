"""Django app configuration for the authentication module."""

from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = __package__
    verbose_name = "Authentication"