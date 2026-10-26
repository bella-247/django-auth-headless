from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from allauth.socialaccount.models import SocialAccount

from .models import AccessToken


def _bearer_user(request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    return AccessToken.authenticate(authorization[7:].strip())


@require_GET
def current_user(request):
    user = request.user if request.user.is_authenticated else _bearer_user(request)
    if user is None:
        return JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401,
        )

    email = user.email
    if not email:
        provider_account = (
            SocialAccount.objects.filter(user=user)
            .exclude(extra_data__email="")
            .first()
        )
        if provider_account:
            email = provider_account.extra_data.get("email", "")

    return JsonResponse(
        {
            "status": 200,
            "data": {
                "user": {
                    "id": user.pk,
                    "username": user.get_username(),
                    "email": email,
                }
            },
        }
    )


@require_GET
def token_callback(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)

    lifetime = timedelta(
        seconds=settings.DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS
    )
    _, raw_token = AccessToken.issue(request.user, lifetime)
    query = urlencode({"token": raw_token})
    return redirect(f"{settings.DJANGO_AUTH_FRONTEND_URL}/account/provider/callback?{query}")


@csrf_exempt
@require_POST
def revoke_token(request):
    authorization = request.headers.get("Authorization", "")
    raw_token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    token = AccessToken.objects.filter(
        token_hash=AccessToken.hash_token(raw_token),
        revoked_at__isnull=True,
    ).first()
    if token:
        token.revoke()
    return JsonResponse({"status": 204}, status=204)
