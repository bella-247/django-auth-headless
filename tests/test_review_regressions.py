import os
from django.conf import settings
from django.test import TestCase, override_settings

from django_allauth_cross_domain.conf import (
    KNOWN_CONFIG_KEYS,
    apply_settings,
    build,
    get_setting,
)
from django_allauth_cross_domain.site_helpers import ensure_site, get_site


class ConfigurationBridgeTests(TestCase):
    def test_get_setting_reads_from_django_auth_dict(self):
        with override_settings(DJANGO_AUTH={"MODE": "cross-domain", "FRONTEND_URL": "https://fe.test"}):
            self.assertEqual(get_setting("MODE"), "cross-domain")
            self.assertEqual(get_setting("FRONTEND_URL"), "https://fe.test")

    def test_get_setting_reads_from_os_environ_when_not_in_settings(self):
        os.environ["DJANGO_AUTH_MODE"] = "cross-domain"
        os.environ["DJANGO_FRONTEND_URL"] = "https://env-frontend.test"
        try:
            with override_settings(DJANGO_AUTH={}):
                self.assertEqual(get_setting("MODE"), "cross-domain")
                self.assertEqual(get_setting("FRONTEND_URL"), "https://env-frontend.test")
        finally:
            os.environ.pop("DJANGO_AUTH_MODE", None)
            os.environ.pop("DJANGO_FRONTEND_URL", None)

    def test_get_setting_type_coercion(self):
        with override_settings(
            DJANGO_AUTH={
                "ACCESS_TOKEN_LIFETIME_SECONDS": "1800",
                "REFRESH_TOKEN_LIFETIME_SECONDS": "7200",
                "ROTATE_REFRESH_TOKENS": "false",
                "ENFORCE_PKCE": "false",
                "MODE": "Cross-Domain",
                "FRONTEND_URL": "https://api.test/ ",
            }
        ):
            self.assertEqual(get_setting("ACCESS_TOKEN_LIFETIME_SECONDS"), 1800)
            self.assertIsInstance(get_setting("ACCESS_TOKEN_LIFETIME_SECONDS"), int)
            self.assertEqual(get_setting("REFRESH_TOKEN_LIFETIME_SECONDS"), 7200)
            self.assertIs(get_setting("ROTATE_REFRESH_TOKENS"), False)
            self.assertIs(get_setting("ENFORCE_PKCE"), False)
            self.assertEqual(get_setting("MODE"), "cross-domain")
            self.assertEqual(get_setting("FRONTEND_URL"), "https://api.test")

    def test_build_includes_enforce_pkce_and_handoff_ttl_and_proxy_trust(self):
        s = build(
            config={
                "ENFORCE_PKCE": True,
                "HANDOFF_CODE_LIFETIME_SECONDS": 45,
                "TRUST_PROXY_HEADERS": True,
            }
        )
        self.assertIn("DJANGO_AUTH_ENFORCE_PKCE", s)
        self.assertTrue(s["DJANGO_AUTH_ENFORCE_PKCE"])
        self.assertIn("DJANGO_AUTH_HANDOFF_CODE_LIFETIME_SECONDS", s)
        self.assertEqual(s["DJANGO_AUTH_HANDOFF_CODE_LIFETIME_SECONDS"], 45)
        self.assertIn("DJANGO_AUTH_TRUST_PROXY_HEADERS", s)
        self.assertTrue(s["DJANGO_AUTH_TRUST_PROXY_HEADERS"])

    def test_build_splits_cors_and_csrf_comma_strings(self):
        s = build(
            config={
                "CORS_ALLOWED_ORIGINS": "https://a.test, https://b.test",
                "CSRF_TRUSTED_ORIGINS": "https://c.test, https://d.test",
            }
        )
        self.assertEqual(s["CORS_ALLOWED_ORIGINS"], ["https://a.test", "https://b.test"])
        self.assertEqual(s["CSRF_TRUSTED_ORIGINS"], ["https://c.test", "https://d.test"])

    def test_build_raises_for_unsupported_provider(self):
        with self.assertRaises(ValueError) as ctx:
            build(config={"PROVIDERS": ["not_a_real_provider"]})
        self.assertIn("Unsupported OAuth provider", str(ctx.exception))

    def test_apply_settings_updates_target_dict(self):
        target = {}
        returned = apply_settings(
            target,
            config={
                "MODE": "cross-domain",
                "FRONTEND_URL": "https://app.test",
                "PROVIDERS": ["google", "github"],
            },
        )
        self.assertEqual(target, returned)
        self.assertEqual(target["DJANGO_AUTH_MODE"], "cross-domain")
        self.assertEqual(target["SITE_ID"], 1)
        self.assertIn("google", target["SOCIALACCOUNT_PROVIDERS"])
        self.assertIn("github", target["SOCIALACCOUNT_PROVIDERS"])
        self.assertEqual(target["ACCOUNT_EMAIL_VERIFICATION"], "mandatory")

    def test_star_import_exports_expected_names(self):
        import django_allauth_cross_domain.conf as conf

        ns = {}
        exec("from django_allauth_cross_domain.conf import *", ns)
        self.assertIn("ACCOUNT_EMAIL_VERIFICATION", ns)
        self.assertIn("SOCIALACCOUNT_PROVIDERS", ns)
        self.assertIn("SITE_ID", ns)
        self.assertIn("apply_settings", ns)
        self.assertIn("build", ns)

    def test_site_helpers_safe_when_site_id_unset(self):
        # Even if settings has no SITE_ID, get_site and ensure_site default to 1 without AttributeError
        site = ensure_site(domain="safe.test", name="Safe Site")
        self.assertEqual(site.domain, "safe.test")
        fetched = get_site()
        self.assertEqual(fetched.domain, "safe.test")

import base64
import hashlib
import json
from datetime import timedelta
from io import StringIO
from urllib.parse import parse_qs

from allauth.socialaccount.models import SocialApp
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from django_allauth_cross_domain.models import AccessToken, OAuthHandoffCode, RefreshToken
from django_allauth_cross_domain.utils import verify_pkce


class SecurityAndInputValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sec-user", password="password")

    def test_verify_pkce_handles_non_ascii_without_500(self):
        # Must return False gracefully without raising TypeError
        self.assertFalse(verify_pkce("é", "abc", "S256"))
        self.assertFalse(verify_pkce("abc", "é", "S256"))
        self.assertFalse(verify_pkce("é", "é", "plain"))

    def test_callback_validates_code_challenge_length_and_charset(self):
        self.client.force_login(self.user)
        with override_settings(DJANGO_AUTH={"MODE": "cross-domain", "FRONTEND_URL": "https://fe.test"}):
            # Too short (<43)
            r_short = self.client.get("/api/auth/callback?code_challenge=short&code_challenge_method=S256")
            self.assertEqual(r_short.status_code, 400)

            # Too long (>128)
            r_long = self.client.get(f"/api/auth/callback?code_challenge={'a' * 150}&code_challenge_method=S256")
            self.assertEqual(r_long.status_code, 400)

            # Non-ASCII character in challenge
            r_na = self.client.get("/api/auth/callback?code_challenge=validchallenge123456789012345678901234567890123%C3%A9&code_challenge_method=S256")
            self.assertEqual(r_na.status_code, 400)

            # Bogus challenge method
            valid_challenge = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
            r_bogus = self.client.get(f"/api/auth/callback?code_challenge={valid_challenge}&code_challenge_method=bogus")
            self.assertEqual(r_bogus.status_code, 400)

    def test_failed_pkce_attempt_immediately_consumes_code(self):
        self.client.force_login(self.user)
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
        with override_settings(DJANGO_AUTH={"MODE": "cross-domain", "FRONTEND_URL": "https://fe.test"}):
            r = self.client.get(f"/api/auth/callback?code_challenge={challenge}&code_challenge_method=S256")
            self.assertEqual(r.status_code, 302)
            raw_code = parse_qs(r["Location"].split("#")[1])["code"][0]

            # Attempt exchange with wrong verifier
            res1 = self.client.post(
                "/api/auth/exchange",
                data=json.dumps({"code": raw_code, "code_verifier": "wrong-verifier-12345678901234567890123456789012"}),
                content_type="application/json",
            )
            self.assertEqual(res1.status_code, 400)

            # Code is now consumed, even legitimate verifier must fail
            res2 = self.client.post(
                "/api/auth/exchange",
                data=json.dumps({"code": raw_code, "code_verifier": verifier}),
                content_type="application/json",
            )
            self.assertEqual(res2.status_code, 400)

    def test_revoke_token_rejects_malformed_bodies_and_returns_empty_204(self):
        # List body
        r1 = self.client.post("/api/auth/token/revoke", data="[]", content_type="application/json")
        self.assertEqual(r1.status_code, 400)

        # Non-string token
        r2 = self.client.post("/api/auth/token/revoke", data='{"token": 123}', content_type="application/json")
        self.assertEqual(r2.status_code, 400)

        # Successful revoke returns HTTP 204 with empty body
        _, raw = AccessToken.issue(self.user, timedelta(hours=1))
        r3 = self.client.post("/api/auth/token/revoke", data=json.dumps({"token": raw}), content_type="application/json")
        self.assertEqual(r3.status_code, 204)
        self.assertEqual(r3.content, b"")
        self.assertEqual(AccessToken.authenticate(raw), None)

    def test_cleanup_tokens_rejects_negative_days(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("cleanup_tokens", days=-1, stdout=out)

    def test_callback_rejects_empty_frontend_url(self):
        self.client.force_login(self.user)
        with override_settings(DJANGO_AUTH={"MODE": "cross-domain", "FRONTEND_URL": ""}):
            r = self.client.get("/api/auth/callback")
            self.assertEqual(r.status_code, 500)

    def test_token_endpoints_include_cache_control_headers(self):
        self.client.force_login(self.user)
        with override_settings(DJANGO_AUTH={"MODE": "cross-domain", "FRONTEND_URL": "https://fe.test"}):
            r_cb = self.client.get("/api/auth/callback")
            self.assertIn("no-store", r_cb.headers.get("Cache-Control", ""))

            _, raw = AccessToken.issue(self.user, timedelta(hours=1))
            r_me = self.client.get("/api/me", HTTP_AUTHORIZATION=f"Bearer {raw}")
            self.assertIn("no-store", r_me.headers.get("Cache-Control", ""))

    def test_refresh_token_reuse_detection_revokes_token_family(self):
        _, raw_refresh = RefreshToken.issue(self.user, timedelta(days=30))
        with override_settings(DJANGO_AUTH={"MODE": "cross-domain", "ROTATE_REFRESH_TOKENS": True}):
            # First legitimate refresh
            r1 = self.client.post(
                "/api/auth/refresh",
                data=json.dumps({"refresh_token": raw_refresh}),
                content_type="application/json",
            )
            self.assertEqual(r1.status_code, 200)
            new_access = r1.json()["data"]["access_token"]
            self.assertIsNotNone(AccessToken.authenticate(new_access))

            # Attempt to replay the old refresh token (adversary re-use attempt!)
            r2 = self.client.post(
                "/api/auth/refresh",
                data=json.dumps({"refresh_token": raw_refresh}),
                content_type="application/json",
            )
            self.assertEqual(r2.status_code, 401)

            # Token reuse detection should have revoked the whole family, including new_access!
            self.assertIsNone(AccessToken.authenticate(new_access))


    def test_direct_password_change_revokes_tokens(self):
        _, raw_access = AccessToken.issue(self.user, timedelta(hours=1))
        self.assertIsNotNone(AccessToken.authenticate(raw_access))

        # Direct set_password and save (like Django Admin or user.set_password)
        self.user.set_password("new_super_secure_password_123")
        self.user.save()

        # Token should be revoked immediately
        self.assertIsNone(AccessToken.authenticate(raw_access))


class ManagementCommandHardeningTests(TestCase):
    def test_setup_oauth_no_input_with_arguments(self):
        out = StringIO()
        call_command(
            "setup_oauth",
            provider="github",
            client_id="gh-client-123",
            client_secret="gh-secret-456",
            domain="localhost:8000",
            no_input=True,
            stdout=out,
        )
        self.assertIn("Created github SocialApp", out.getvalue())
        app = SocialApp.objects.filter(provider="github").first()
        self.assertIsNotNone(app)
        self.assertEqual(app.client_id, "gh-client-123")

    def test_setup_oauth_handles_multiple_existing_social_apps_without_error(self):
        # Create duplicate social apps for same provider
        SocialApp.objects.create(provider="gitlab", client_id="gl-1", secret="gl-s-1", name="Gitlab 1")
        SocialApp.objects.create(provider="gitlab", client_id="gl-2", secret="gl-s-2", name="Gitlab 2")

        out = StringIO()
        # Should update without raising MultipleObjectsReturned
        call_command(
            "setup_oauth",
            provider="gitlab",
            client_id="gl-updated",
            client_secret="gl-secret-updated",
            no_input=True,
            stdout=out,
        )
        self.assertIn("Created gitlab SocialApp", out.getvalue())

    def test_verify_oauth_runs_with_ascii_safe_output(self):
        out = StringIO()
        call_command("verify_oauth", stdout=out)
        val = out.getvalue()
        self.assertIn("=== OAuth Configuration Verification ===", val)
        self.assertIn("[OK]", val)


class SessionModeDisabledEndpointsTests(TestCase):
    def test_cross_domain_endpoints_return_404_in_session_mode(self):
        with override_settings(DJANGO_AUTH={"MODE": "session"}):
            r_cb = self.client.get("/api/auth/callback")
            self.assertEqual(r_cb.status_code, 404)

            r_ex = self.client.post("/api/auth/exchange", data='{"code": "abc"}', content_type="application/json")
            self.assertEqual(r_ex.status_code, 404)

            r_ref = self.client.post("/api/auth/refresh", data='{"refresh_token": "abc"}', content_type="application/json")
            self.assertEqual(r_ref.status_code, 404)

            r_rev = self.client.post("/api/auth/token/revoke", data='{"token": "abc"}', content_type="application/json")
            self.assertEqual(r_rev.status_code, 404)
