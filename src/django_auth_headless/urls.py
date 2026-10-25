"""URL patterns for django-allauth headless and social authentication."""

from django.urls import include, path

from .views import current_user

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path("api/me", current_user, name="current_user"),
]