"""Management command to clean up expired authentication tokens and handoff codes."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...models import AccessToken, OAuthHandoffCode, RefreshToken


class Command(BaseCommand):
    help = "Delete expired AccessTokens, RefreshTokens, and OAuthHandoffCodes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=0,
            help="Purge records expired more than N days ago (default: 0).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 0:
            raise CommandError("--days must be a non-negative integer.")

        cutoff = timezone.now() - timedelta(days=days)

        deleted_access, _ = AccessToken.objects.filter(expires_at__lt=cutoff).delete()
        deleted_refresh, _ = RefreshToken.objects.filter(expires_at__lt=cutoff).delete()
        deleted_codes, _ = OAuthHandoffCode.objects.filter(expires_at__lt=cutoff).delete()

        total = deleted_access + deleted_refresh + deleted_codes
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {total} expired token records "
                f"({deleted_access} access tokens, {deleted_refresh} refresh tokens, {deleted_codes} handoff codes)."
            )
        )
