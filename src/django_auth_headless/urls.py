"""URL patterns for django-allauth headless and social authentication."""

from django.urls import include, path

from .views import current_user, exchange_code, revoke_token, token_callback

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path("api/me", current_user, name="current_user"),
    path("api/auth/callback", token_callback, name="token_callback"),
    path("api/auth/exchange", exchange_code, name="exchange_code"),
    path("api/auth/token/revoke", revoke_token, name="revoke_token"),
]