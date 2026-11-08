from .models import AccessToken


class BearerTokenMiddleware:
    """Middleware that authenticates requests using Bearer AccessTokens.

    If request.user is already authenticated (e.g. via session cookies), this
    middleware leaves it unchanged. If unauthenticated and a Bearer token is
    supplied in the HTTP Authorization header, it validates the token and
    assigns the matching user to request.user.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                raw_token = auth_header[7:].strip()
                if raw_token:
                    authenticated_user = AccessToken.authenticate(raw_token)
                    if authenticated_user:
                        request.user = authenticated_user

        return self.get_response(request)

