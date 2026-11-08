from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .conf import get_setting
from .models import AccessToken, OAuthHandoffCode
from .serializers import get_user_payload


def _require_cross_domain_mode():
    mode = get_setting("MODE", getattr(settings, "DJANGO_AUTH_MODE", "session"))
    if mode != "cross-domain":
        return JsonResponse(
            {"detail": "Cross-domain token authentication is not enabled."},
            status=404,
        )
    return None


def _bearer_user(request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    return AccessToken.authenticate(authorization[7:].strip())


@require_GET
def current_user(request):
    user = request.user if request.user.is_authenticated else _bearer_user(request)
    if user is None or not user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401,
        )

    return JsonResponse(
        {
            "status": 200,
            "data": {"user": get_user_payload(user)},
        }
    )


@require_GET
def token_callback(request):
    mode_error = _require_cross_domain_mode()
    if mode_error:
        return mode_error
    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401,
        )

    _, raw_code = OAuthHandoffCode.issue(request.user, timedelta(minutes=5))
    query = urlencode({"code": raw_code})
    frontend_url = get_setting(
        "FRONTEND_URL", getattr(settings, "DJANGO_AUTH_FRONTEND_URL", "")
    ).rstrip("/")
    return redirect(
        f"{frontend_url}/account/provider/callback#{query}"
    )


@csrf_exempt
@require_POST
def exchange_code(request):
    mode_error = _require_cross_domain_mode()
    if mode_error:
        return mode_error
    import json

    try:
        payload = json.loads(request.body)
        raw_code = payload["code"]
    except (TypeError, ValueError, KeyError):
        return JsonResponse(
            {"detail": "A valid authorization code is required."}, status=400
        )

    if not isinstance(raw_code, str) or not raw_code:
        return JsonResponse(
            {"detail": "A valid authorization code is required."}, status=400
        )

    user = OAuthHandoffCode.redeem(raw_code)
    if user is None:
        return JsonResponse(
            {"detail": "The authorization code is invalid or expired."}, status=400
        )

    lifetime = get_setting(
        "ACCESS_TOKEN_LIFETIME_SECONDS",
        getattr(settings, "DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS", 3600),
    )
    _, raw_token = AccessToken.issue(
        user,
        timedelta(seconds=lifetime),
    )
    return JsonResponse(
        {
            "status": 200,
            "data": {
                "access_token": raw_token,
                "expires_in": lifetime,
            },
        }
    )


@csrf_exempt
@require_POST
def revoke_token(request):
    mode_error = _require_cross_domain_mode()
    if mode_error:
        return mode_error
    authorization = request.headers.get("Authorization", "")
    raw_token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    token = AccessToken.objects.filter(
        token_hash=AccessToken.hash_token(raw_token),
        revoked_at__isnull=True,
    ).first()
    if token:
        token.revoke()
    return JsonResponse({"status": 204}, status=204)
