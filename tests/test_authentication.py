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
        self.assertIn("refresh_token", response.json()["data"])

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

    def test_build_defaults_to_session_mode(self):
        settings = build({})
        self.assertEqual(settings["DJANGO_AUTH_MODE"], "session")

    def test_build_accepts_cross_domain_mode(self):
        settings = build({"DJANGO_AUTH_MODE": "cross-domain"})
        self.assertEqual(settings["DJANGO_AUTH_MODE"], "cross-domain")

    def test_build_rejects_invalid_auth_mode(self):
        with self.assertRaises(ValueError):
            build({"DJANGO_AUTH_MODE": "token"})

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

    def test_build_defaults_for_security_controls(self):
        settings = build({})
        self.assertEqual(settings["ACCOUNT_EMAIL_VERIFICATION"], "mandatory")
        self.assertFalse(settings["SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT"])

    def test_build_with_django_auth_config_dict(self):
        config = {
            "FRONTEND_URL": "http://frontend.example.com",
            "MODE": "cross-domain",
            "PROVIDERS": ["google", "github"],
            "EMAIL_VERIFICATION": "optional",
            "EMAIL_AUTO_CONNECT": True,
            "ACCESS_TOKEN_LIFETIME_SECONDS": 7200,
            "USER_SERIALIZER": "myproject.serializers.custom_user",
        }
        settings = build(config=config)
        self.assertEqual(settings["DJANGO_AUTH_FRONTEND_URL"], "http://frontend.example.com")
        self.assertEqual(settings["DJANGO_AUTH_MODE"], "cross-domain")
        self.assertEqual(settings["DJANGO_ACCESS_TOKEN_LIFETIME_SECONDS"], 7200)
        self.assertEqual(settings["ACCOUNT_EMAIL_VERIFICATION"], "optional")
        self.assertTrue(settings["SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT"])
        self.assertIn("google", settings["SOCIALACCOUNT_PROVIDERS"])
        self.assertIn("github", settings["SOCIALACCOUNT_PROVIDERS"])
        self.assertEqual(
            settings["HEADLESS_FRONTEND_URLS"]["account_signup"],
            "http://frontend.example.com/account/signup",
        )
        self.assertEqual(settings["DJANGO_AUTH_USER_SERIALIZER"], "myproject.serializers.custom_user")

    def test_build_rejects_invalid_email_verification(self):
        with self.assertRaises(ValueError):
            build(config={"EMAIL_VERIFICATION": "invalid_setting"})

    def test_build_accepts_providers_as_comma_separated_string(self):
        settings = build(config={"PROVIDERS": "google, gitlab"})
        self.assertIn("google", settings["SOCIALACCOUNT_PROVIDERS"])
        self.assertIn("gitlab", settings["SOCIALACCOUNT_PROVIDERS"])
        self.assertNotIn("github", settings["SOCIALACCOUNT_PROVIDERS"])

    def test_get_setting_resolves_from_django_auth_dict(self):
        from django_auth_headless.conf import get_setting
        from django.test import override_settings

        with override_settings(DJANGO_AUTH={"MODE": "cross-domain", "FRONTEND_URL": "http://override.test"}):
            self.assertEqual(get_setting("MODE"), "cross-domain")
            self.assertEqual(get_setting("FRONTEND_URL"), "http://override.test")
            self.assertEqual(get_setting("NON_EXISTENT", default="fallback"), "fallback")

    def test_app_config_ready_populates_settings_from_django_auth(self):
        from django.apps import apps
        from django.conf import settings as django_settings
        from django.test import override_settings

        app_config = apps.get_app_config("django_auth_headless")
        with override_settings(
            DJANGO_AUTH={
                "FRONTEND_URL": "http://auto-app.test",
                "MODE": "cross-domain",
                "EMAIL_VERIFICATION": "mandatory",
                "EMAIL_AUTO_CONNECT": False,
                "PROVIDERS": ["google"],
            }
        ):
            # Simulate ready()
            app_config.ready()
            self.assertEqual(django_settings.ACCOUNT_EMAIL_VERIFICATION, "mandatory")
            self.assertFalse(django_settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT)
            self.assertIn("google", django_settings.SOCIALACCOUNT_PROVIDERS)
            self.assertEqual(
                django_settings.HEADLESS_FRONTEND_URLS["account_signup"],
                "http://auto-app.test/account/signup",
            )

    def test_token_callback_uses_django_auth_frontend_url(self):
        from django.test import override_settings

        user = get_user_model().objects.create_user(
            username="callback-tester", password="password"
        )
        self.client.force_login(user)
        with override_settings(
            DJANGO_AUTH={
                "MODE": "cross-domain",
                "FRONTEND_URL": "https://frontend.custom.org",
            }
        ):
            response = self.client.get("/api/auth/callback")
            self.assertEqual(response.status_code, 302)
            self.assertTrue(
                response["Location"].startswith("https://frontend.custom.org/account/provider/callback#code=")
            )

    def test_exchange_code_uses_django_auth_token_lifetime(self):
        from django.test import override_settings

        user = get_user_model().objects.create_user(
            username="exchange-tester", password="password"
        )
        _, raw_code = OAuthHandoffCode.issue(user, timedelta(minutes=5))
        with override_settings(
            DJANGO_AUTH={
                "MODE": "cross-domain",
                "ACCESS_TOKEN_LIFETIME_SECONDS": 1800,
            }
        ):
            response = self.client.post(
                "/api/auth/exchange",
                data={"code": raw_code},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["expires_in"], 1800)

    def test_verify_oauth_management_command(self):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("verify_oauth", stdout=out)
        output = out.getvalue()
        self.assertIn("OAuth Configuration Verification", output)
        self.assertIn("Site Configuration", output)
        self.assertIn("Social Applications", output)

    def test_setup_oauth_management_command(self):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command(
            "setup_oauth",
            provider="github",
            client_id="github-client-id",
            client_secret="github-client-secret",
            domain="localhost:8000",
            stdout=out,
        )
        output = out.getvalue()
        self.assertIn("Created github SocialApp for site localhost:8000", output)
        app = SocialApp.objects.get(provider="github")
        self.assertEqual(app.client_id, "github-client-id")
        self.assertEqual(app.secret, "github-client-secret")

    def test_refresh_token_endpoint_rotates_tokens(self):
        from django_auth_headless.models import RefreshToken

        user = get_user_model().objects.create_user(
            username="refresh-user", password="password"
        )
        _, raw_refresh = RefreshToken.issue(user, timedelta(days=30))

        # Refresh
        response = self.client.post(
            "/api/auth/refresh",
            data={"refresh_token": raw_refresh},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertNotEqual(data["refresh_token"], raw_refresh)

        # Authenticate with the new access token
        me_resp = self.client.get(
            "/api/me",
            HTTP_AUTHORIZATION=f"Bearer {data['access_token']}",
        )
        self.assertEqual(me_resp.status_code, 200)

        # Old refresh token is now revoked
        old_resp = self.client.post(
            "/api/auth/refresh",
            data={"refresh_token": raw_refresh},
            content_type="application/json",
        )
        self.assertEqual(old_resp.status_code, 401)

    def test_refresh_token_without_rotation(self):
        from django_auth_headless.models import RefreshToken
        from django.test import override_settings

        user = get_user_model().objects.create_user(
            username="no-rotate-user", password="password"
        )
        _, raw_refresh = RefreshToken.issue(user, timedelta(days=30))

        with override_settings(
            DJANGO_AUTH={
                "MODE": "cross-domain",
                "ROTATE_REFRESH_TOKENS": False,
            }
        ):
            response = self.client.post(
                "/api/auth/refresh",
                data={"refresh_token": raw_refresh},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["refresh_token"], raw_refresh)

    def test_refresh_token_validation_errors(self):
        # Missing token
        r1 = self.client.post(
            "/api/auth/refresh",
            data={},
            content_type="application/json",
        )
        self.assertEqual(r1.status_code, 400)

        # Invalid token
        r2 = self.client.post(
            "/api/auth/refresh",
            data={"refresh_token": "nonexistent-token"},
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 401)

    def test_revoke_refresh_token(self):
        from django_auth_headless.models import RefreshToken

        user = get_user_model().objects.create_user(
            username="revoke-refresh-user", password="password"
        )
        _, raw_refresh = RefreshToken.issue(user, timedelta(days=30))

        # Revoke via POST body
        revoke_resp = self.client.post(
            "/api/auth/token/revoke",
            data={"token": raw_refresh},
            content_type="application/json",
        )
        self.assertEqual(revoke_resp.status_code, 204)

        # Attempt to use revoked refresh token
        refresh_resp = self.client.post(
            "/api/auth/refresh",
            data={"refresh_token": raw_refresh},
            content_type="application/json",
        )
        self.assertEqual(refresh_resp.status_code, 401)

    def test_cleanup_tokens_management_command(self):
        from io import StringIO
        from django.core.management import call_command
        from django_auth_headless.models import AccessToken, OAuthHandoffCode, RefreshToken

        user = get_user_model().objects.create_user(
            username="cleanup-user", password="password"
        )

        # Create expired and active tokens
        AccessToken.issue(user, timedelta(seconds=-10))
        _, active_access = AccessToken.issue(user, timedelta(hours=1))

        RefreshToken.issue(user, timedelta(seconds=-10))
        _, active_refresh = RefreshToken.issue(user, timedelta(days=30))

        OAuthHandoffCode.issue(user, timedelta(seconds=-10))
        _, active_code = OAuthHandoffCode.issue(user, timedelta(minutes=5))

        out = StringIO()
        call_command("cleanup_tokens", days=0, stdout=out)
        self.assertIn("Successfully deleted 3 expired token records", out.getvalue())

        # Verify active items remain
        self.assertIsNotNone(AccessToken.authenticate(active_access))
        self.assertIsNotNone(RefreshToken.authenticate(active_refresh))
        self.assertIsNotNone(OAuthHandoffCode.redeem(active_code))

    def test_apple_oauth_provider_support(self):
        from django_auth_headless.conf import AUTH_APPS, build

        self.assertIn("allauth.socialaccount.providers.apple", AUTH_APPS)
        settings = build({"DJANGO_AUTH_PROVIDERS": "apple"})
        self.assertIn("apple", settings["SOCIALACCOUNT_PROVIDERS"])




