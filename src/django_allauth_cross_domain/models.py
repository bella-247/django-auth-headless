import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import models
from django.db import transaction
from django.utils import timezone

from .utils import verify_pkce


class BaseToken(models.Model):
    """Abstract base model for hashed, revocable tokens."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def revoke(self) -> None:
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])

    @classmethod
    def revoke_all_for_user(cls, user) -> int:
        """Revoke all active tokens for a given user."""
        return cls.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )


class AccessToken(BaseToken):
    @classmethod
    def issue(cls, user, lifetime):
        raw_token = secrets.token_urlsafe(48)
        token = cls.objects.create(
            user=user,
            token_hash=cls.hash_token(raw_token),
            expires_at=timezone.now() + lifetime,
        )
        return token, raw_token

    @classmethod
    def authenticate(cls, raw_token: str):
        if not raw_token or not isinstance(raw_token, str):
            return None
        token = (
            cls.objects.select_related("user")
            .filter(
                token_hash=cls.hash_token(raw_token),
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if token and getattr(token.user, "is_active", True):
            return token.user
        return None


class OAuthHandoffCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64, unique=True)
    code_challenge = models.CharField(max_length=128, blank=True, default="")
    code_challenge_method = models.CharField(max_length=10, blank=True, default="S256")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, user, lifetime, code_challenge="", code_challenge_method="S256"):
        raw_code = secrets.token_urlsafe(32)
        code = cls.objects.create(
            user=user,
            code_hash=AccessToken.hash_token(raw_code),
            code_challenge=code_challenge or "",
            code_challenge_method=code_challenge_method or "S256" if code_challenge else "",
            expires_at=timezone.now() + lifetime,
        )
        return code, raw_code

    @classmethod
    def redeem(cls, raw_code: str, code_verifier: str | None = None):
        if not raw_code or not isinstance(raw_code, str):
            return None
        with transaction.atomic():
            code = (
                cls.objects.select_for_update()
                .select_related("user")
                .filter(
                    code_hash=AccessToken.hash_token(raw_code),
                    used_at__isnull=True,
                    expires_at__gt=timezone.now(),
                )
                .first()
            )
            if code is None or not getattr(code.user, "is_active", True):
                return None

            # PKCE validation: if a code_challenge was registered at issuance,
            # code_verifier is mandatory and must match the challenge.
            if code.code_challenge:
                if not code_verifier or not verify_pkce(
                    code_verifier, code.code_challenge, code.code_challenge_method
                ):
                    # Immediately consume the code on failure to prevent brute-force attacks
                    code.used_at = timezone.now()
                    code.save(update_fields=["used_at"])
                    return None

            code.used_at = timezone.now()
            code.save(update_fields=["used_at"])
            return code.user

    @classmethod
    def invalidate_all_for_user(cls, user) -> int:
        """Invalidate all unredeemed handoff codes for a given user."""
        return cls.objects.filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )


class RefreshToken(BaseToken):
    @classmethod
    def issue(cls, user, lifetime):
        raw_token = secrets.token_urlsafe(64)
        token = cls.objects.create(
            user=user,
            token_hash=cls.hash_token(raw_token),
            expires_at=timezone.now() + lifetime,
        )
        return token, raw_token

    @classmethod
    def authenticate(cls, raw_token: str):
        if not raw_token or not isinstance(raw_token, str):
            return None
        token = (
            cls.objects.select_related("user")
            .filter(
                token_hash=cls.hash_token(raw_token),
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if token and getattr(token.user, "is_active", True):
            return token
        return None

    @classmethod
    def rotate(
        cls,
        raw_refresh: str,
        access_lifetime_seconds: int,
        refresh_lifetime_seconds: int,
        rotate: bool = True,
    ) -> tuple[Any | None, str | None, str | None, str | None]:
        """Atomically rotate a refresh token with token reuse detection (RFC 6749).

        Returns:
            (user, new_raw_access, new_raw_refresh, error_code)
            error_code: None, "invalid", "revoked_reuse", "expired", "inactive"
        """
        if not raw_refresh or not isinstance(raw_refresh, str):
            return None, None, None, "invalid"

        token_hash = cls.hash_token(raw_refresh)

        with transaction.atomic():
            token_record = (
                cls.objects.select_for_update()
                .select_related("user")
                .filter(token_hash=token_hash)
                .first()
            )

            if token_record is None:
                return None, None, None, "invalid"

            # Reuse detection: if a revoked refresh token is presented, revoke the entire token family
            if token_record.revoked_at is not None:
                revoke_all_tokens_for_user(token_record.user)
                return None, None, None, "revoked_reuse"

            if token_record.expires_at <= timezone.now():
                return None, None, None, "expired"

            user = token_record.user
            if not getattr(user, "is_active", True):
                return None, None, None, "inactive"

            if rotate:
                token_record.revoked_at = timezone.now()
                token_record.save(update_fields=["revoked_at"])
                _, new_raw_refresh = cls.issue(
                    user, timedelta(seconds=refresh_lifetime_seconds)
                )
            else:
                new_raw_refresh = raw_refresh

            _, new_raw_access = AccessToken.issue(
                user, timedelta(seconds=access_lifetime_seconds)
            )

            return user, new_raw_access, new_raw_refresh, None


def revoke_all_tokens_for_user(user) -> None:
    """Revoke all active access tokens, refresh tokens, and handoff codes for a user."""
    AccessToken.revoke_all_for_user(user)
    RefreshToken.revoke_all_for_user(user)
    OAuthHandoffCode.invalidate_all_for_user(user)
