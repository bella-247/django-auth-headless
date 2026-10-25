"""Management command to verify OAuth configuration."""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

from ...conf import PROVIDER_CONFIGS, build
from ...site_helpers import get_site


class Command(BaseCommand):
    help = "Verify OAuth configuration: Site, SocialApp, providers, env vars"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== OAuth Configuration Verification ===\n"))

        all_ok = True

        # 1. Check Site
        all_ok &= self._check_site()

        # 2. Check SocialApp(s)
        all_ok &= self._check_social_apps()

        # 3. Check env vars
        all_ok &= self._check_env_vars()

        # 4. Check allauth config endpoint
        all_ok &= self._check_allauth_config()

        # Summary
        self.stdout.write("")
        if all_ok:
            self.stdout.write(self.style.SUCCESS("✓ All checks passed"))
        else:
            self.stdout.write(self.style.ERROR("✗ Some checks failed"))

        return ""

    def _check_site(self) -> bool:
        self.stdout.write("1. Site Configuration:")
        try:
            site = get_site()
            self.stdout.write(f"   ✓ Site ID {site.pk}: {site.domain} ({site.name})")
            return True
        except Site.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"   ✗ Site with ID {settings.SITE_ID} does not exist"))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ✗ Error: {e}"))
            return False

    def _check_social_apps(self) -> bool:
        self.stdout.write("\n2. Social Applications:")
        providers = build()["SOCIALACCOUNT_PROVIDERS"]
        if not providers:
            self.stdout.write(self.style.WARNING("   ⚠ No providers configured in env"))
            return True

        all_ok = True
        for provider_id, config in providers.items():
            try:
                app = SocialApp.objects.get(provider=provider_id)
                sites = list(app.sites.values_list("domain", flat=True))
                self.stdout.write(f"   ✓ {provider_id}: {app.name} (sites: {', '.join(sites) or 'none'})")
            except SocialApp.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"   ✗ {provider_id}: SocialApp not found in database"))
                all_ok = False
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ✗ {provider_id}: Error - {e}"))
                all_ok = False
        return all_ok

    def _check_env_vars(self) -> bool:
        self.stdout.write("\n3. Environment Variables:")
        all_ok = True
        for provider_id, config in PROVIDER_CONFIGS.items():
            client_id = config["client_id_env"]
            client_secret = config["client_secret_env"]
            has_id = bool(settings.__dict__.get(client_id) or getattr(settings, client_id, None))
            has_secret = bool(settings.__dict__.get(client_secret) or getattr(settings, client_secret, None))

            # Check actual env
            import os
            has_id = bool(os.getenv(client_id))
            has_secret = bool(os.getenv(client_secret))

            if has_id and has_secret:
                self.stdout.write(f"   ✓ {provider_id}: {client_id}, {client_secret} present")
            elif has_id or has_secret:
                self.stdout.write(self.style.WARNING(f"   ⚠ {provider_id}: Only one of {client_id}/{client_secret} set"))
                all_ok = False
            else:
                self.stdout.write(f"   ○ {provider_id}: Not configured (optional)")
        return all_ok

    def _check_allauth_config(self) -> bool:
        self.stdout.write("\n4. Allauth Headless Config Endpoint:")
        try:
            from django.test import Client
            client = Client(HTTP_HOST="localhost:8000")
            response = client.get("/_allauth/browser/v1/config", HTTP_ORIGIN="http://localhost:5173")

            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"   ✗ Config endpoint returned {response.status_code}"))
                return False

            data = response.json()
            providers = data.get("data", {}).get("socialaccount", {}).get("providers", [])

            if not providers:
                self.stdout.write(self.style.WARNING("   ⚠ No providers in allauth config"))
                return True

            self.stdout.write(f"   ✓ Config endpoint accessible, {len(providers)} provider(s) found")
            for p in providers:
                self.stdout.write(f"      - {p['id']}: {p['name']} (flows: {', '.join(p['flows'])})")
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ✗ Config endpoint error: {e}"))
            return False