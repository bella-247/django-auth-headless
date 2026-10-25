"""Management command to configure OAuth provider credentials."""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from getpass import getpass

from ...site_helpers import ensure_site


class Command(BaseCommand):
    help = "Configure OAuth provider: prompts for credentials, updates .env, creates SocialApp"

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            default="google",
            choices=["google", "github", "gitlab", "microsoft"],
            help="OAuth provider to configure (default: google)",
        )
        parser.add_argument(
            "--client-id",
            help="OAuth client ID (skip interactive prompt)",
        )
        parser.add_argument(
            "--client-secret",
            help="OAuth client secret (skip interactive prompt)",
        )
        parser.add_argument(
            "--domain",
            default="localhost:8000",
            help="Site domain for the OAuth callback (default: localhost:8000)",
        )
        parser.add_argument(
            "--name",
            help="Site display name (default: provider title + domain)",
        )
        parser.add_argument(
            "--env-file",
            help="Path to .env file to update (default: backend/.env)",
        )

    def handle(self, *args, **options):
        provider = options["provider"]
        client_id = options["client_id"] or input(f"{provider.title()} Client ID: ").strip()
        client_secret = options["client_secret"] or getpass(f"{provider.title()} Client Secret: ")
        domain = options["domain"]
        name = options["name"] or f"{provider.title()} Auth ({domain})"
        env_file = options["env_file"]

        if not client_id or not client_secret:
            raise CommandError("Client ID and secret are required")

        # Ensure Site
        site = ensure_site(domain, name)

        # Create/update SocialApp
        app, created = SocialApp.objects.update_or_create(
            provider=provider,
            defaults={
                "name": f"{provider.title()} OAuth",
                "client_id": client_id,
                "secret": client_secret,
            },
        )
        app.sites.add(site)

        self.stdout.write(self.style.SUCCESS(f"Created {provider} SocialApp for site {domain}"))
        self.stdout.write("Add these to your .env:")
        self.stdout.write(f"  DJANGO_{provider.upper()}_CLIENT_ID={client_id}")
        self.stdout.write(f"  DJANGO_{provider.upper()}_CLIENT_SECRET={client_secret}")

        # Optionally update .env file
        if env_file:
            self._update_env_file(env_file, provider, client_id, client_secret)
            self.stdout.write(self.style.SUCCESS(f"Updated {env_file}"))

    def _update_env_file(self, env_file: str, provider: str, client_id: str, client_secret: str) -> None:
        """Update .env file with provider credentials."""
        from pathlib import Path

        path = Path(env_file)
        lines = []
        if path.exists():
            lines = path.read_text().splitlines()

        # Remove existing provider credentials
        client_id_key = f"DJANGO_{provider.upper()}_CLIENT_ID"
        client_secret_key = f"DJANGO_{provider.upper()}_CLIENT_SECRET"
        lines = [l for l in lines if not l.startswith(f"{client_id_key}=") and not l.startswith(f"{client_secret_key}=")]

        # Add new credentials
        lines.append(f"{client_id_key}={client_id}")
        lines.append(f"{client_secret_key}={client_secret}")

        path.write_text("\n".join(lines) + "\n")