import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db import transaction
from django.utils import timezone


class AccessToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, user, lifetime):
        raw_token = secrets.token_urlsafe(48)
        token = cls.objects.create(
            user=user,
            token_hash=cls.hash_token(raw_token),
            expires_at=timezone.now() + lifetime,
        )
        return token, raw_token

    @staticmethod
    def hash_token(raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def authenticate(cls, raw_token):
        token = cls.objects.select_related("user").filter(
            token_hash=cls.hash_token(raw_token),
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()
        return token.user if token else None

    def revoke(self):
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])


class OAuthHandoffCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, user, lifetime):
        raw_code = secrets.token_urlsafe(32)
        code = cls.objects.create(
            user=user,
            code_hash=AccessToken.hash_token(raw_code),
            expires_at=timezone.now() + lifetime,
        )
        return code, raw_code

    @classmethod
    def redeem(cls, raw_code):
        with transaction.atomic():
            code = cls.objects.select_for_update().select_related("user").filter(
                code_hash=AccessToken.hash_token(raw_code),
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).first()
            if code is None:
                return None
            code.used_at = timezone.now()
            code.save(update_fields=["used_at"])
            return code.user
