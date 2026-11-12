import json
import logging
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .conf import get_setting
from .models import AccessToken, OAuthHandoffCode, RefreshToken
from .serializers import get_user_payload
from .utils.pkce import is_valid_pkce_string

logger = logging.getLogger("django_allauth_cross_domain")


def _with_cache_control(response: HttpResponse) -> HttpResponse:
    """Add strict anti-caching headers (RFC 6749 Section 5.1)."""
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


def _error_response(
    detail: str, status: int = 400, code: str | None = None
) -> JsonResponse:
    """Return an error JSON envelope satisfying both DRF and Allauth Headless conventions."""
    payload = {
        "status": status,
        "detail": detail,
        "errors": [{"message": detail, "code": code or "invalid"}],
    }
    return _with_cache_control(JsonResponse(payload, status=status))


def _get_client_ip(request) -> str:
    """Extract client IP address for security audit logging with optional proxy trust."""
    trust_proxy = get_setting(
        "TRUST_PROXY_HEADERS",
        getattr(settings, "DJANGO_AUTH_TRUST_PROXY_HEADERS", False),
    )
    if trust_proxy:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _require_cross_domain_mode():
    mode = get_setting("MODE", getattr(settings, "DJANGO_AUTH_MODE", "session"))
    if mode != "cross-domain":
        return _error_response(
            "Cross-domain token authentication is not enabled.",
            status=404,
            code="mode_disabled",
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
        response = _error_response(
            "Authentication credentials were not provided.",
            status=401,
            code="authentication_required",
        )
        response["WWW-Authenticate"] = "Bearer"
        return response

    response = JsonResponse(
        {
            "status": 200,
            "data": {"user": get_user_payload(user)},
        }
    )
    return _with_cache_control(response)


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
        return _error_response(
            "Authentication credentials were not provided.",
            status=401,
            code="authentication_required",
        )

    frontend_url = get_setting(
        "FRONTEND_URL", getattr(settings, "DJANGO_AUTH_FRONTEND_URL", "")
    )
    if not frontend_url or not (
        frontend_url.startswith("http://") or frontend_url.startswith("https://")
    ):
        logger.error("DJANGO_AUTH['FRONTEND_URL'] is not configured or not an absolute URL")
        return _error_response(
            "DJANGO_AUTH['FRONTEND_URL'] is not configured or invalid.",
            status=500,
            code="invalid_configuration",
        )
    frontend_url = frontend_url.rstrip("/")

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
        return _error_response(
            "A code_challenge parameter is required when PKCE is enforced.",
            status=400,
            code="pkce_required",
        )

    if code_challenge:
        if not is_valid_pkce_string(code_challenge):
            return _error_response(
                "Invalid code_challenge: must be 43-128 unreserved ASCII characters (RFC 7636).",
                status=400,
                code="invalid_code_challenge",
            )
        if code_challenge_method.upper() not in {"S256", "PLAIN"}:
            return _error_response(
                "Invalid code_challenge_method: must be S256 or plain.",
                status=400,
                code="invalid_code_challenge_method",
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
    response = redirect(f"{frontend_url}/account/provider/callback#{query}")
    return _with_cache_control(response)


@csrf_exempt
@require_POST
def exchange_code(request):
    mode_error = _require_cross_domain_mode()
    if mode_error:
        return mode_error

    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            return _error_response("A valid JSON object is required.", status=400, code="invalid_json")
        raw_code = payload.get("code")
        code_verifier = payload.get("code_verifier", None)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _error_response("A valid authorization code is required.", status=400, code="invalid_payload")

    if not isinstance(raw_code, str) or not raw_code:
        return _error_response("A valid authorization code is required.", status=400, code="invalid_code")

    if code_verifier is not None and not isinstance(code_verifier, str):
        return _error_response("code_verifier must be a string.", status=400, code="invalid_verifier")

    user = OAuthHandoffCode.redeem(raw_code, code_verifier=code_verifier)
    if user is None:
        logger.warning(
            "Rejected code exchange from ip=%s: invalid/expired code or PKCE verifier mismatch",
            _get_client_ip(request),
        )
        return _error_response(
            "The authorization code is invalid or expired.",
            status=400,
            code="invalid_or_expired_code",
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
    return _with_cache_control(response)


@csrf_exempt
@require_POST
def refresh_token(request):
    mode_error = _require_cross_domain_mode()
    if mode_error:
        return mode_error

    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            return _error_response("A valid JSON object is required.", status=400, code="invalid_json")
        raw_refresh = payload.get("refresh_token")
    except (TypeError, ValueError, json.JSONDecodeError):
        return _error_response("A valid refresh token is required.", status=400, code="invalid_payload")

    if not isinstance(raw_refresh, str) or not raw_refresh:
        return _error_response("A valid refresh token is required.", status=400, code="invalid_token")

    rotate = get_setting(
        "ROTATE_REFRESH_TOKENS",
        getattr(settings, "DJANGO_AUTH_ROTATE_REFRESH_TOKENS", True),
    )
    access_lifetime = get_setting(
        "ACCESS_TOKEN_LIFETIME_SECONDS",
        getattr(settings, "DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS", 3600),
    )
    refresh_lifetime = get_setting(
        "REFRESH_TOKEN_LIFETIME_SECONDS",
        getattr(settings, "DJANGO_REFRESH_TOKEN_LIFETIME_SECONDS", 2592000),
    )

    user, new_raw_access, new_raw_refresh, error_code = RefreshToken.rotate(
        raw_refresh,
        access_lifetime_seconds=access_lifetime,
        refresh_lifetime_seconds=refresh_lifetime,
        rotate=rotate,
    )

    if error_code == "revoked_reuse":
        logger.warning(
            "ALERT: Refresh token reuse detected from ip=%s. Revoked token family.",
            _get_client_ip(request),
        )
        response = _error_response(
            "Refresh token reuse detected. All tokens revoked.",
            status=401,
            code="token_reuse",
        )
        response["WWW-Authenticate"] = "Bearer"
        return response

    if error_code or user is None:
        logger.warning(
            "Rejected token refresh attempt from ip=%s: token invalid, expired, or revoked (code=%s)",
            _get_client_ip(request),
            error_code,
        )
        response = _error_response(
            "The refresh token is invalid or expired.",
            status=401,
            code="invalid_token",
        )
        response["WWW-Authenticate"] = "Bearer"
        return response

    logger.info(
        "Refreshed access token for user_id=%s from ip=%s",
        user.pk,
        _get_client_ip(request),
    )

    response = JsonResponse(
        {
            "status": 200,
            "data": {
                "access_token": new_raw_access,
                "refresh_token": new_raw_refresh,
                "expires_in": access_lifetime,
            },
        }
    )
    return _with_cache_control(response)


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
        try:
            payload = json.loads(request.body)
            if not isinstance(payload, dict):
                return _error_response(
                    "Invalid payload: expected JSON object.",
                    status=400,
                    code="invalid_json",
                )
            token_val = payload.get("token") or payload.get("refresh_token") or ""
            if token_val and not isinstance(token_val, str):
                return _error_response(
                    "Token must be a string.",
                    status=400,
                    code="invalid_token_type",
                )
            raw_token = token_val.strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            return _error_response(
                "Invalid JSON body.",
                status=400,
                code="invalid_json",
            )

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

    response = HttpResponse(status=204)
    return _with_cache_control(response)
