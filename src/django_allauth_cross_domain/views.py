import logging
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .conf import get_setting
from .models import AccessToken, OAuthHandoffCode, RefreshToken
from .serializers import get_user_payload

logger = logging.getLogger("django_allauth_cross_domain")


def _get_client_ip(request) -> str:
    """Extract client IP address for security audit logging."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


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
    if user is None or not user.is_authenticated or not getattr(user, "is_active", True):
        logger.debug("Unauthenticated /api/me request from ip=%s", _get_client_ip(request))
        response = JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401,
        )
        response["WWW-Authenticate"] = "Bearer"
        return response

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
    if not request.user.is_authenticated or not getattr(request.user, "is_active", True):
        logger.warning(
            "Unauthenticated /api/auth/callback request from ip=%s",
            _get_client_ip(request),
        )
        return JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401,
        )

    code_challenge = request.GET.get("code_challenge", "").strip()
    code_challenge_method = request.GET.get("code_challenge_method", "S256").strip()

    enforce_pkce = get_setting(
        "ENFORCE_PKCE",
        getattr(settings, "DJANGO_AUTH_ENFORCE_PKCE", False),
    )
    if enforce_pkce and not code_challenge:
        logger.warning(
            "Rejected callback from ip=%s: code_challenge is required when PKCE is enforced",
            _get_client_ip(request),
        )
        return JsonResponse(
            {"detail": "A code_challenge parameter is required when PKCE is enforced."},
            status=400,
        )

    handoff_ttl = get_setting(
        "HANDOFF_CODE_LIFETIME_SECONDS",
        getattr(settings, "DJANGO_AUTH_HANDOFF_CODE_LIFETIME_SECONDS", 60),
    )
    _, raw_code = OAuthHandoffCode.issue(
        request.user,
        timedelta(seconds=handoff_ttl),
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
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
        code_verifier = payload.get("code_verifier", None)
    except (TypeError, ValueError, KeyError):
        return JsonResponse(
            {"detail": "A valid authorization code is required."}, status=400
        )

    if not isinstance(raw_code, str) or not raw_code:
        return JsonResponse(
            {"detail": "A valid authorization code is required."}, status=400
        )

    user = OAuthHandoffCode.redeem(raw_code, code_verifier=code_verifier)
    if user is None:
        logger.warning(
            "Rejected code exchange from ip=%s: invalid/expired code or PKCE verifier mismatch",
            _get_client_ip(request),
        )
        return JsonResponse(
            {"detail": "The authorization code is invalid or expired."}, status=400
        )

    logger.info(
        "Successfully exchanged authorization code for user_id=%s from ip=%s",
        user.pk,
        _get_client_ip(request),
    )

    lifetime = get_setting(
        "ACCESS_TOKEN_LIFETIME_SECONDS",
        getattr(settings, "DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS", 3600),
    )
    refresh_lifetime = get_setting(
        "REFRESH_TOKEN_LIFETIME_SECONDS",
        getattr(settings, "DJANGO_REFRESH_TOKEN_LIFETIME_SECONDS", 2592000),
    )
    _, raw_token = AccessToken.issue(
        user,
        timedelta(seconds=lifetime),
    )
    _, raw_refresh_token = RefreshToken.issue(
        user,
        timedelta(seconds=refresh_lifetime),
    )
    response = JsonResponse(
        {
            "status": 200,
            "data": {
                "access_token": raw_token,
                "refresh_token": raw_refresh_token,
                "expires_in": lifetime,
            },
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@csrf_exempt
@require_POST
def refresh_token(request):
    mode_error = _require_cross_domain_mode()
    if mode_error:
        return mode_error

    import json

    try:
        payload = json.loads(request.body)
        raw_refresh = payload["refresh_token"]
    except (TypeError, ValueError, KeyError):
        return JsonResponse(
            {"detail": "A valid refresh token is required."}, status=400
        )

    if not isinstance(raw_refresh, str) or not raw_refresh:
        return JsonResponse(
            {"detail": "A valid refresh token is required."}, status=400
        )

    token_record = RefreshToken.authenticate(raw_refresh)
    if token_record is None:
        logger.warning(
            "Rejected token refresh attempt from ip=%s: token invalid, expired, or revoked",
            _get_client_ip(request),
        )
        response = JsonResponse(
            {"detail": "The refresh token is invalid or expired."}, status=401
        )
        response["WWW-Authenticate"] = "Bearer"
        return response

    user = token_record.user
    rotate = get_setting(
        "ROTATE_REFRESH_TOKENS",
        getattr(settings, "DJANGO_AUTH_ROTATE_REFRESH_TOKENS", True),
    )
    if rotate:
        token_record.revoke()
        refresh_lifetime = get_setting(
            "REFRESH_TOKEN_LIFETIME_SECONDS",
            getattr(settings, "DJANGO_REFRESH_TOKEN_LIFETIME_SECONDS", 2592000),
        )
        _, new_refresh_token = RefreshToken.issue(
            user, timedelta(seconds=refresh_lifetime)
        )
    else:
        new_refresh_token = raw_refresh

    access_lifetime = get_setting(
        "ACCESS_TOKEN_LIFETIME_SECONDS",
        getattr(settings, "DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS", 3600),
    )
    _, new_access_token = AccessToken.issue(
        user, timedelta(seconds=access_lifetime)
    )

    logger.info(
        "Refreshed access token for user_id=%s from ip=%s",
        user.pk,
        _get_client_ip(request),
    )

    response = JsonResponse(
        {
            "status": 200,
            "data": {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_in": access_lifetime,
            },
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@csrf_exempt
@require_POST
def revoke_token(request):
    mode_error = _require_cross_domain_mode()
    if mode_error:
        return mode_error

    raw_token = ""
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        raw_token = authorization[7:].strip()
    elif request.body:
        import json

        try:
            payload = json.loads(request.body)
            raw_token = payload.get("token") or payload.get("refresh_token") or ""
        except (TypeError, ValueError):
            pass

    if raw_token:
        token_hash = AccessToken.hash_token(raw_token)
        access_tok = AccessToken.objects.filter(
            token_hash=token_hash,
            revoked_at__isnull=True,
        ).first()
        if access_tok:
            access_tok.revoke()
            logger.info(
                "Revoked access token for user_id=%s from ip=%s",
                access_tok.user_id,
                _get_client_ip(request),
            )

        refresh_tok = RefreshToken.objects.filter(
            token_hash=token_hash,
            revoked_at__isnull=True,
        ).first()
        if refresh_tok:
            refresh_tok.revoke()
            logger.info(
                "Revoked refresh token for user_id=%s from ip=%s",
                refresh_tok.user_id,
                _get_client_ip(request),
            )

    return JsonResponse({"status": 204}, status=204)

