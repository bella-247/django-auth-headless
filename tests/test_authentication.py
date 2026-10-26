import tempfile
from datetime import timedelta
from datetime import timedelta
from pathlib import Path

from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model
from django.test import TestCase

from allauth.socialaccount.models import SocialApp

from django_auth_headless.conf import build
from django_auth_headless.site_helpers import ensure_site
from django_auth_headless.urls import urlpatterns as auth_urlpatterns
from django_auth_headless.utils import load_env_file
from django_auth_headless.models import AccessToken
from django_auth_headless.models import OAuthHandoffCode


class AuthenticationPackageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        site = Site.objects.get(pk=1)
        site.domain = "testserver"
        site.name = "testserver"
        site.save()
        app = SocialApp.objects.create(
            provider="google",
            name="Google Test OAuth",
            client_id="test.apps.googleusercontent.com",
            secret="test-secret",
        )
        app.sites.add(site)

    def test_headless_config_lists_google(self):
        response = self.client.get(
            "/_allauth/browser/v1/config",
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], 200)
        providers = response.json()["data"]["socialaccount"]["providers"]
        self.assertIn("google", {provider["id"] for provider in providers})

    def test_current_user_requires_authentication(self):
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 401)

    def test_current_user_returns_structured_data(self):
        user = get_user_model().objects.create_user(
            username="test-user",
            email="test@example.com",
            password="password",
        )
        self.client.force_login(user)
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["user"]["email"], "test@example.com")

    def test_current_user_accepts_database_backed_bearer_token(self):
        user = get_user_model().objects.create_user(
            username="token-user",
            email="token@example.com",
            password="password",
        )
        _, raw_token = AccessToken.issue(user, timedelta(hours=1))
        response = self.client.get(
            "/api/me",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_authorization_code_exchange_is_single_use(self):
        user = get_user_model().objects.create_user(
            username="exchange-user",
            password="password",
        )
        _, raw_code = OAuthHandoffCode.issue(user, timedelta(minutes=5))

        response = self.client.post(
            "/api/auth/exchange",
            data={"code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json()["data"])

        second_response = self.client.post(
            "/api/auth/exchange",
            data={"code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(second_response.status_code, 400)

    def test_expired_bearer_token_is_rejected(self):
        user = get_user_model().objects.create_user(username="expired-user")
        _, raw_token = AccessToken.issue(user, timedelta(seconds=-1))
        response = self.client.get(
            "/api/me",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(response.status_code, 401)

    def test_build_does_not_create_settings_backed_apps(self):
        settings = build({"DJANGO_AUTH_PROVIDERS": "google,github"})
        self.assertNotIn("APP", settings["SOCIALACCOUNT_PROVIDERS"]["google"])
        self.assertNotIn("APP", settings["SOCIALACCOUNT_PROVIDERS"]["github"])

    def test_build_supports_same_site_cookie_configuration(self):
        settings = build(
            {
                "DJANGO_SESSION_COOKIE_DOMAIN": ".example.com",
                "DJANGO_SESSION_COOKIE_SECURE": "true",
                "DJANGO_CSRF_COOKIE_SECURE": "true",
                "DJANGO_SESSION_COOKIE_SAMESITE": "Lax",
                "DJANGO_CSRF_COOKIE_SAMESITE": "Lax",
            }
        )
        self.assertEqual(settings["SESSION_COOKIE_DOMAIN"], ".example.com")
        self.assertEqual(settings["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_build_rejects_invalid_samesite_value(self):
        with self.assertRaises(ValueError):
            build({"DJANGO_SESSION_COOKIE_SAMESITE": "invalid"})

    def test_build_requires_secure_cookie_for_samesite_none(self):
        with self.assertRaises(ValueError):
            build({"DJANGO_SESSION_COOKIE_SAMESITE": "None"})

    def test_custom_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "custom.env"
            with env_file.open("w") as file:
                file.write("TEST_VAR=custom_value\n")
            test_env = {}
            load_env_file(env_file, test_env)
            self.assertEqual(test_env["TEST_VAR"], "custom_value")

    def test_urlpatterns_include_package_routes(self):
        routes = [str(pattern.pattern) for pattern in auth_urlpatterns]
        self.assertTrue(any("api/me" in route for route in routes))

    def test_ensure_site_updates_existing_site(self):
        updated = ensure_site("new.example", "New")
        self.assertEqual(updated.pk, 1)
        self.assertEqual(updated.domain, "new.example")
