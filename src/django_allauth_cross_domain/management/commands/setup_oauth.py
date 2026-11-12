"""Management command to configure OAuth provider credentials."""

import os
from getpass import getpass
from pathlib import Path

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError

from ...site_helpers import ensure_site


class Command(BaseCommand):
    help = "Configure OAuth provider: prompts for credentials, updates .env, creates SocialApp"

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            default="google",
            choices=["google", "github", "gitlab", "microsoft", "apple"],
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
            "--key",
            help="Key ID (required for Apple OAuth)",
        )
        parser.add_argument(
            "--certificate-key",
            help="Certificate / Private key PEM (required for Apple OAuth)",
        )
        parser.add_argument(
            "--team-id",
            help="Developer Team ID (required for Apple OAuth)",
        )
        parser.add_argument(
            "--domain",
            help="Site domain for OAuth callback (default: current site domain or localhost:8000)",
        )
        parser.add_argument(
            "--name",
            help="Site display name (default: provider title + domain)",
        )
        parser.add_argument(
            "--env-file",
            help="Path to .env file to update (e.g. .env)",
        )
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Do not prompt for input; read missing values from environment variables.",
        )

    def handle(self, *args, **options):
        provider = options["provider"]
        no_input = options.get("no_input", False)

        client_id = options.get("client_id")
        client_secret = options.get("client_secret")
        key = options.get("key")
        certificate_key = options.get("certificate_key")
        team_id = options.get("team_id")

        if no_input:
            client_id = client_id or os.environ.get(f"DJANGO_{provider.upper()}_CLIENT_ID", "")
            client_secret = client_secret or os.environ.get(f"DJANGO_{provider.upper()}_CLIENT_SECRET", "")
            if provider == "apple":
                key = key or os.environ.get("DJANGO_APPLE_KEY", "")
                certificate_key = certificate_key or os.environ.get("DJANGO_APPLE_CERTIFICATE_KEY", "")
                team_id = team_id or os.environ.get("DJANGO_APPLE_TEAM_ID", "")
        else:
            if not client_id:
                client_id = input(f"{provider.title()} Client ID: ").strip()
            if not client_secret:
                client_secret = getpass(f"{provider.title()} Client Secret: ").strip()
            if provider == "apple":
                if not key:
                    key = input("Apple Key ID: ").strip()
                if not team_id:
                    team_id = input("Apple Team ID: ").strip()
                if not certificate_key:
                    certificate_key = getpass("Apple Certificate / Private Key: ").strip()

        if not client_id or not client_secret:
            raise CommandError("Client ID and secret are required")

        domain = options.get("domain")
        if not domain:
            try:
                from django.conf import settings
                site_id = getattr(settings, "SITE_ID", 1)
                domain = Site.objects.get(pk=site_id).domain
            except Exception:
                domain = "localhost:8000"

        name = options.get("name") or f"{provider.title()} Auth ({domain})"
        env_file = options.get("env_file")

        site = ensure_site(domain, name)

        app_defaults = {
            "name": f"{provider.title()} OAuth",
            "client_id": client_id,
            "secret": client_secret,
        }
        if provider == "apple":
            if key:
                app_defaults["key"] = key
            if certificate_key:
                app_defaults["certificate_key"] = certificate_key
            if team_id:
                app_defaults["settings"] = {"team_id": team_id}

        app = SocialApp.objects.filter(provider=provider).first()
        if app:
            for attr, val in app_defaults.items():
                setattr(app, attr, val)
            app.save()
        else:
            app = SocialApp.objects.create(provider=provider, **app_defaults)

        app.sites.add(site)

        self.stdout.write(self.style.SUCCESS(f"Created {provider} SocialApp for site {domain}"))
        self.stdout.write("Configured environment credentials:")
        self.stdout.write(f"  DJANGO_{provider.upper()}_CLIENT_ID={client_id}")
        self.stdout.write(f"  DJANGO_{provider.upper()}_CLIENT_SECRET=*** (hidden)")

        if env_file:
            self._update_env_file(env_file, provider, client_id, client_secret)
            self.stdout.write(self.style.SUCCESS(f"Updated {env_file}"))

    def _update_env_file(self, env_file: str, provider: str, client_id: str, client_secret: str) -> None:
        """Update .env file with provider credentials and enforce secure permissions."""
        path = Path(env_file)
        lines = []
        if path.exists():
            lines = path.read_text().splitlines()

        client_id_key = f"DJANGO_{provider.upper()}_CLIENT_ID"
        client_secret_key = f"DJANGO_{provider.upper()}_CLIENT_SECRET"

        filtered = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("export "):
                stripped = stripped[7:].strip()
            if stripped.startswith(f"{client_id_key}=") or stripped.startswith(f"{client_secret_key}="):
                continue
            filtered.append(line)

        # Quote values safely
        def safe_val(val: str) -> str:
            if " " in val or "\n" in val or '"' in val:
                escaped = val.replace('"', '\\"')
                return f'"{escaped}"'
            return val

        filtered.append(f"{client_id_key}={safe_val(client_id)}")
        filtered.append(f"{client_secret_key}={safe_val(client_secret)}")

        path.write_text("\n".join(filtered) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
