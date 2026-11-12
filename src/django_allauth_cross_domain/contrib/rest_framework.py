"""Django REST Framework integration for django-allauth-cross-domain."""

try:
    from rest_framework.authentication import BaseAuthentication
    from rest_framework.exceptions import AuthenticationFailed
except ImportError as exc:
    raise ImportError(
        "djangorestframework is required to use django_allauth_cross_domain.contrib.rest_framework. "
        "Install it with `pip install django-allauth-cross-domain[drf]`."
    ) from exc

from ..models import AccessToken


class BearerTokenAuthentication(BaseAuthentication):
    """DRF Authentication class using django-allauth-cross-domain AccessTokens.

    Unlike session-based authentication, this authenticator bypasses CSRF checks
    for API requests while authenticating Bearer tokens.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None

        raw_token = auth_header[len(self.keyword) + 1 :].strip()
        if not raw_token:
            return None

        user = AccessToken.authenticate(raw_token)
        if user is None:
            raise AuthenticationFailed("Invalid, expired, or inactive access token.")

        return (user, raw_token)

    def authenticate_header(self, request):
        return self.keyword
