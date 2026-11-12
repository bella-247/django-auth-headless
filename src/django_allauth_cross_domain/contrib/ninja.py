"""Django Ninja integration for django-auth-headless."""

try:
    from ninja.security import HttpBearer
except ImportError:  # pragma: no cover
    HttpBearer = object  # type: ignore[misc,assignment]

from ..models import AccessToken


class BearerAuth(HttpBearer):
    """Django Ninja bearer authentication using django-auth-headless AccessTokens."""

    def authenticate(self, request, token):
        user = AccessToken.authenticate(token)
        if user is not None:
            return user
        return None

