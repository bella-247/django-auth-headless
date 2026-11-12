"""Management command to verify OAuth configuration."""

import os
from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.urls import resolve, Resolver404

from ...conf import PROVIDER_CONFIGS, build, get_setting
from ...site_helpers import get_site


class Command(BaseCommand):
    help = "Verify OAuth configuration: Site, SocialApp, providers, env vars"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== OAuth Configuration Verification ===\n"))

        all_ok = True

        all_ok &= self._check_site()
        all_ok &= self._check_social_apps()
        all_ok &= self._check_env_vars()
        all_ok &= self._check_allauth_config()

        self.stdout.write("")
        if all_ok:
            self.stdout.write(self.style.SUCCESS("[OK] All checks passed"))
        else:
            self.stdout.write(self.style.ERROR("[FAIL] Some checks failed"))

        return ""

    def _check_site(self) -> bool:
        self.stdout.write("1. Site Configuration:")
        try:
            site = get_site()
            self.stdout.write(f"   [OK] Site ID {site.pk}: {site.domain} ({site.name})")
            return True
        except Site.DoesNotExist:
            site_id = getattr(settings, "SITE_ID", 1)
            self.stdout.write(self.style.ERROR(f"   [FAIL] Site with ID {site_id} does not exist"))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   [FAIL] Error: {e}"))
            return False

    def _check_social_apps(self) -> bool:
        self.stdout.write("\n2. Social Applications:")
        providers = (
            getattr(settings, "SOCIALACCOUNT_PROVIDERS", None)
            or build().get("SOCIALACCOUNT_PROVIDERS", {})
        )
        if not providers:
            self.stdout.write(self.style.WARNING("   [WARN] No providers configured"))
            return True

        all_ok = True
        for provider_id in providers.keys():
            apps = list(SocialApp.objects.filter(provider=provider_id))
            if apps:
                app = apps[0]
                sites = list(app.sites.values_list("domain", flat=True))
                count_str = f" ({len(apps)} app records)" if len(apps) > 1 else ""
                self.stdout.write(f"   [OK] {provider_id}: {app.name}{count_str} (sites: {', '.join(sites) or 'none'})")
            else:
                self.stdout.write(self.style.ERROR(f"   [FAIL] {provider_id}: SocialApp not found in database"))
                all_ok = False
        return all_ok

    def _check_env_vars(self) -> bool:
        self.stdout.write("\n3. Environment Variables:")
        all_ok = True
        for provider_id, config in PROVIDER_CONFIGS.items():
            client_id_env = config["client_id_env"]
            client_secret_env = config["client_secret_env"]

            has_id = bool(os.getenv(client_id_env) or getattr(settings, client_id_env, None))
            has_secret = bool(os.getenv(client_secret_env) or getattr(settings, client_secret_env, None))

            if has_id and has_secret:
                self.stdout.write(f"   [OK] {provider_id}: {client_id_env}, {client_secret_env} present")
            elif has_id or has_secret:
                self.stdout.write(self.style.WARNING(f"   [WARN] {provider_id}: Only one of {client_id_env}/{client_secret_env} set"))
                all_ok = False
            else:
                self.stdout.write(f"   [INFO] {provider_id}: Not configured (optional)")
        return all_ok

    def _check_allauth_config(self) -> bool:
        self.stdout.write("\n4. Allauth Headless Config Endpoint:")
        endpoint = "/_allauth/browser/v1/config"
        try:
            site_domain = "localhost:8000"
            try:
                site = get_site()
                site_domain = site.domain
            except Exception:
                pass

            frontend_url = get_setting(
                "FRONTEND_URL",
                getattr(settings, "DJANGO_AUTH_FRONTEND_URL", "http://localhost:5173"),
            )

            try:
                match = resolve(endpoint)
            except Resolver404:
                self.stdout.write(self.style.WARNING("   [WARN] Allauth headless URLs not registered under /_allauth/"))
                return True

            factory = RequestFactory(HTTP_HOST=site_domain)
            request = factory.get(endpoint, HTTP_ORIGIN=frontend_url)
            response = match.func(request, *match.args, **match.kwargs)

            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"   [FAIL] Config endpoint returned {response.status_code}"))
                return False

            self.stdout.write("   [OK] Config endpoint reachable and resolved successfully")
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   [FAIL] Config endpoint check error: {e}"))
            return False
