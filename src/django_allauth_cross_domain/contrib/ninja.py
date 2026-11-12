"""Django Ninja integration for django-allauth-cross-domain."""

try:
    from ninja.security import HttpBearer
except ImportError as exc:
    raise ImportError(
        "django-ninja is required to use django_allauth_cross_domain.contrib.ninja. "
        "Install it with `pip install django-allauth-cross-domain[ninja]`."
    ) from exc

from ..models import AccessToken


class BearerAuth(HttpBearer):
    """Django Ninja bearer authentication using django-allauth-cross-domain AccessTokens."""

    def authenticate(self, request, token):
        user = AccessToken.authenticate(token)
        if user is not None:
            return user
        return None
