import tempfile
from datetime import timedelta
from datetime import timedelta
from pathlib import Path

from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model
from django.test import TestCase

from allauth.socialaccount.models import SocialApp

from django_allauth_cross_domain.conf import build
from django_allauth_cross_domain.site_helpers import ensure_site
from django_allauth_cross_domain.urls import urlpatterns as auth_urlpatterns
from django_allauth_cross_domain.utils import load_env_file
from django_allauth_cross_domain.models import AccessToken, OAuthHandoffCode, RefreshToken


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
        from django_allauth_cross_domain.conf import get_setting
        from django.test import override_settings

        with override_settings(DJANGO_AUTH={"MODE": "cross-domain", "FRONTEND_URL": "http://override.test"}):
            self.assertEqual(get_setting("MODE"), "cross-domain")
            self.assertEqual(get_setting("FRONTEND_URL"), "http://override.test")
            self.assertEqual(get_setting("NON_EXISTENT", default="fallback"), "fallback")

    def test_app_config_ready_does_not_mutate_settings(self):
        from django.apps import apps
        from django.conf import settings as django_settings
        from django.test import override_settings

        app_config = apps.get_app_config("django_allauth_cross_domain")
        with override_settings(
            ACCOUNT_EMAIL_VERIFICATION="none",
            DJANGO_AUTH={
                "FRONTEND_URL": "http://auto-app.test",
                "MODE": "cross-domain",
                "EMAIL_VERIFICATION": "mandatory",
                "EMAIL_AUTO_CONNECT": False,
                "PROVIDERS": ["google"],
            },
        ):
            # Simulate ready()
            app_config.ready()
            # Explicit user setting must NEVER be clobbered by ready()
            self.assertEqual(django_settings.ACCOUNT_EMAIL_VERIFICATION, "none")

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
        from django_allauth_cross_domain.models import RefreshToken

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
        from django_allauth_cross_domain.models import RefreshToken
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
        from django_allauth_cross_domain.models import RefreshToken

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
        from django_allauth_cross_domain.models import AccessToken, OAuthHandoffCode, RefreshToken

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
        from django_allauth_cross_domain.conf import AUTH_APPS, build

        self.assertIn("allauth.socialaccount.providers.apple", AUTH_APPS)
        settings = build({"DJANGO_AUTH_PROVIDERS": "apple"})
        self.assertIn("apple", settings["SOCIALACCOUNT_PROVIDERS"])

    def test_inactive_user_cannot_authenticate_with_bearer_token(self):
        user = get_user_model().objects.create_user(
            username="inactive-user", password="password", is_active=False
        )
        _, raw_token = AccessToken.issue(user, timedelta(hours=1))

        # Direct model authentication must reject inactive user
        self.assertIsNone(AccessToken.authenticate(raw_token))

        # Current user endpoint must reject with 401 and WWW-Authenticate header
        response = self.client.get(
            "/api/me", HTTP_AUTHORIZATION=f"Bearer {raw_token}"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")

    def test_inactive_user_cannot_redeem_handoff_code(self):
        user = get_user_model().objects.create_user(
            username="inactive-oauth-user", password="password", is_active=False
        )
        _, raw_code = OAuthHandoffCode.issue(user, timedelta(minutes=5))
        self.assertIsNone(OAuthHandoffCode.redeem(raw_code))

    def test_inactive_user_cannot_refresh_token(self):
        user = get_user_model().objects.create_user(
            username="inactive-refresh-user", password="password", is_active=False
        )
        _, raw_refresh = RefreshToken.issue(user, timedelta(days=30))
        self.assertIsNone(RefreshToken.authenticate(raw_refresh))

        response = self.client.post(
            "/api/auth/refresh",
            data={"refresh_token": raw_refresh},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")

    def test_build_parses_string_booleans_safely(self):
        settings_false = build(
            config={
                "EMAIL_AUTO_CONNECT": "false",
                "ROTATE_REFRESH_TOKENS": "0",
                "SESSION_COOKIE_SECURE": "no",
                "CSRF_COOKIE_SECURE": "off",
            }
        )
        self.assertFalse(settings_false["SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT"])
        self.assertFalse(settings_false["DJANGO_AUTH_ROTATE_REFRESH_TOKENS"])
        self.assertFalse(settings_false["SESSION_COOKIE_SECURE"])
        self.assertFalse(settings_false["CSRF_COOKIE_SECURE"])

        settings_true = build(
            config={
                "EMAIL_AUTO_CONNECT": "true",
                "ROTATE_REFRESH_TOKENS": "1",
                "SESSION_COOKIE_SECURE": "yes",
                "CSRF_COOKIE_SECURE": "on",
            }
        )
        self.assertTrue(settings_true["SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT"])
        self.assertTrue(settings_true["DJANGO_AUTH_ROTATE_REFRESH_TOKENS"])
        self.assertTrue(settings_true["SESSION_COOKIE_SECURE"])
        self.assertTrue(settings_true["CSRF_COOKIE_SECURE"])

    def test_build_rejects_unknown_config_keys(self):
        with self.assertRaises(ValueError) as ctx:
            build(config={"UNRECOGNIZED_OPTION": True})
        self.assertIn("Unknown DJANGO_AUTH configuration key", str(ctx.exception))

    def test_security_headers_on_token_endpoints(self):
        user = get_user_model().objects.create_user(
            username="sec-headers-user", password="password"
        )
        _, raw_code = OAuthHandoffCode.issue(user, timedelta(minutes=1))

        # /api/auth/exchange has Cache-Control: no-store
        resp = self.client.post(
            "/api/auth/exchange",
            data={"code": raw_code},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Cache-Control"), "no-store")
        refresh_token = resp.json()["data"]["refresh_token"]

        # /api/auth/refresh has Cache-Control: no-store
        refresh_resp = self.client.post(
            "/api/auth/refresh",
            data={"refresh_token": refresh_token},
            content_type="application/json",
        )
        self.assertEqual(refresh_resp.status_code, 200)
        self.assertEqual(refresh_resp.headers.get("Cache-Control"), "no-store")

    def test_setup_oauth_masks_secret_and_secures_env_file(self):
        import os
        import stat
        import tempfile
        from io import StringIO
        from django.core.management import call_command

        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            temp_env = tf.name

        try:
            out = StringIO()
            call_command(
                "setup_oauth",
                provider="google",
                client_id="my-client-id",
                client_secret="super-secret-value-12345",
                domain="api.example.com",
                env_file=temp_env,
                stdout=out,
            )
            output = out.getvalue()
            # Must NOT expose client secret in stdout
            self.assertNotIn("super-secret-value-12345", output)
            self.assertIn("DJANGO_GOOGLE_CLIENT_SECRET=*** (hidden)", output)

            # File mode must be 0o600
            file_mode = stat.S_IMODE(os.stat(temp_env).st_mode)
            self.assertEqual(file_mode, 0o600)
        finally:
            if os.path.exists(temp_env):
                os.remove(temp_env)

    def test_token_callback_issues_60s_handoff_code(self):
        from django.test import override_settings

        user = get_user_model().objects.create_user(
            username="ttl-user", password="password"
        )
        self.client.force_login(user)
        with override_settings(
            DJANGO_AUTH={
                "MODE": "cross-domain",
                "FRONTEND_URL": "https://frontend.custom.org",
            }
        ):
            resp = self.client.get("/api/auth/callback")
            self.assertEqual(resp.status_code, 302)
            code_record = OAuthHandoffCode.objects.filter(user=user).latest("created_at")
            remaining = (code_record.expires_at - code_record.created_at).total_seconds()
            self.assertAlmostEqual(remaining, 60, delta=2)

    def test_verify_pkce_rfc7636_test_vector(self):
        from django_allauth_cross_domain.utils import verify_pkce

        # RFC 7636 Appendix B test vector
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

        # Correct verifier matches challenge
        self.assertTrue(verify_pkce(verifier, challenge, "S256"))
        # Wrong verifier fails
        self.assertFalse(verify_pkce("wrong-verifier-12345", challenge, "S256"))
        # Plain method
        self.assertTrue(verify_pkce("plain-secret", "plain-secret", "plain"))
        self.assertFalse(verify_pkce("plain-secret", "wrong-secret", "plain"))

    def test_pkce_cross_domain_handoff_exchange(self):
        from django.test import override_settings
        import urllib.parse

        user = get_user_model().objects.create_user(
            username="pkce-user", password="password"
        )
        self.client.force_login(user)

        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

        with override_settings(
            DJANGO_AUTH={
                "MODE": "cross-domain",
                "FRONTEND_URL": "https://frontend.custom.org",
            }
        ):
            # Callback with code_challenge
            resp = self.client.get(
                f"/api/auth/callback?code_challenge={challenge}&code_challenge_method=S256"
            )
            self.assertEqual(resp.status_code, 302)
            location = resp["Location"]
            raw_code = urllib.parse.parse_qs(location.split("#")[1])["code"][0]

            # Attempt 1: Exchange without code_verifier fails (stolen code by adversary)
            fail_resp1 = self.client.post(
                "/api/auth/exchange",
                data={"code": raw_code},
                content_type="application/json",
            )
            self.assertEqual(fail_resp1.status_code, 400)

            # Attempt 2: Exchange with invalid code_verifier fails
            fail_resp2 = self.client.post(
                "/api/auth/exchange",
                data={"code": raw_code, "code_verifier": "attacker-guess"},
                content_type="application/json",
            )
            self.assertEqual(fail_resp2.status_code, 400)

            # Attempt 3: Exchange with legitimate code_verifier succeeds
            success_resp = self.client.post(
                "/api/auth/exchange",
                data={"code": raw_code, "code_verifier": verifier},
                content_type="application/json",
            )
            self.assertEqual(success_resp.status_code, 200)
            self.assertIn("access_token", success_resp.json()["data"])
            self.assertIn("refresh_token", success_resp.json()["data"])

    def test_enforce_pkce_rejects_requests_without_challenge(self):
        from django.test import override_settings

        user = get_user_model().objects.create_user(
            username="enforce-pkce-user", password="password"
        )
        self.client.force_login(user)

        with override_settings(
            DJANGO_AUTH={
                "MODE": "cross-domain",
                "FRONTEND_URL": "https://frontend.custom.org",
                "ENFORCE_PKCE": True,
            }
        ):
            # Without code_challenge, request is rejected with 400
            resp = self.client.get("/api/auth/callback")
            self.assertEqual(resp.status_code, 400)
            self.assertIn("code_challenge parameter is required", resp.json()["detail"])

    def test_drf_bearer_token_authentication(self):
        from rest_framework.exceptions import AuthenticationFailed
        from rest_framework.test import APIRequestFactory
        from django_allauth_cross_domain.contrib.rest_framework import BearerTokenAuthentication

        user = get_user_model().objects.create_user(
            username="drf-user", password="password"
        )
        _, raw_token = AccessToken.issue(user, timedelta(hours=1))

        factory = APIRequestFactory()
        authenticator = BearerTokenAuthentication()

        # Non-bearer request returns None
        req1 = factory.get("/api/test")
        self.assertIsNone(authenticator.authenticate(req1))

        # Valid bearer token returns (user, token)
        req2 = factory.get("/api/test", HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        auth_result = authenticator.authenticate(req2)
        self.assertIsNotNone(auth_result)
        self.assertEqual(auth_result[0], user)
        self.assertEqual(auth_result[1], raw_token)
        self.assertEqual(authenticator.authenticate_header(req2), "Bearer")

        # Invalid token raises AuthenticationFailed
        req3 = factory.get("/api/test", HTTP_AUTHORIZATION="Bearer invalid-token-string")
        with self.assertRaises(AuthenticationFailed):
            authenticator.authenticate(req3)

    def test_ninja_bearer_auth(self):
        from django.test import RequestFactory
        from django_allauth_cross_domain.contrib.ninja import BearerAuth

        user = get_user_model().objects.create_user(
            username="ninja-user", password="password"
        )
        _, raw_token = AccessToken.issue(user, timedelta(hours=1))

        factory = RequestFactory()
        auth = BearerAuth()
        req = factory.get("/api/test")

        # Valid token
        self.assertEqual(auth.authenticate(req, raw_token), user)

        # Invalid token
        self.assertIsNone(auth.authenticate(req, "invalid-token-string"))

    def test_signal_token_revocation_on_password_change(self):
        from allauth.account.signals import password_changed

        user = get_user_model().objects.create_user(
            username="pw-change-user", password="old-password"
        )
        _, raw_access = AccessToken.issue(user, timedelta(hours=1))
        _, raw_refresh = RefreshToken.issue(user, timedelta(days=30))

        # Both tokens are initially valid
        self.assertIsNotNone(AccessToken.authenticate(raw_access))
        self.assertIsNotNone(RefreshToken.authenticate(raw_refresh))

        # Fire allauth password_changed signal
        password_changed.send(sender=user.__class__, request=None, user=user)

        # Both tokens must now be revoked
        self.assertIsNone(AccessToken.authenticate(raw_access))
        self.assertIsNone(RefreshToken.authenticate(raw_refresh))

    def test_signal_token_revocation_on_user_deactivation(self):
        user = get_user_model().objects.create_user(
            username="deactivate-user", password="password"
        )
        _, raw_access = AccessToken.issue(user, timedelta(hours=1))
        _, raw_refresh = RefreshToken.issue(user, timedelta(days=30))

        self.assertIsNotNone(AccessToken.authenticate(raw_access))
        self.assertIsNotNone(RefreshToken.authenticate(raw_refresh))

        # Deactivate user and save
        user.is_active = False
        user.save()

        # Both tokens must be revoked
        self.assertIsNone(AccessToken.authenticate(raw_access))
        self.assertIsNone(RefreshToken.authenticate(raw_refresh))

    def test_models_have_database_indices_on_expires_at(self):
        self.assertTrue(AccessToken._meta.get_field("expires_at").db_index)
        self.assertTrue(RefreshToken._meta.get_field("expires_at").db_index)
        self.assertTrue(OAuthHandoffCode._meta.get_field("expires_at").db_index)







