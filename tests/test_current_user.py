from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from allauth.socialaccount.models import SocialAccount


def sample_custom_serializer(user):
    return {
        "id": user.pk,
        "username": user.get_username(),
        "custom_role": "admin",
        "avatar": "https://example.com/avatar.png",
    }


class CurrentUserEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="me-tester",
            email="tester@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_current_user_returns_connected_providers(self):
        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="google-uid-123",
            extra_data={"email": "tester@example.com"},
        )
        SocialAccount.objects.create(
            user=self.user,
            provider="github",
            uid="github-uid-456",
            extra_data={"email": "tester@example.com"},
        )

        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        user_data = response.json()["data"]["user"]
        self.assertIn("connected_providers", user_data)
        self.assertCountEqual(user_data["connected_providers"], ["google", "github"])

    @override_settings(
        DJANGO_AUTH_USER_SERIALIZER="tests.test_current_user.sample_custom_serializer"
    )
    def test_current_user_uses_custom_serializer(self):
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        user_data = response.json()["data"]["user"]
        self.assertEqual(user_data["custom_role"], "admin")
        self.assertEqual(user_data["avatar"], "https://example.com/avatar.png")

    @override_settings(
        DJANGO_AUTH={"USER_SERIALIZER": sample_custom_serializer}
    )
    def test_current_user_uses_serializer_from_django_auth_dict(self):
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 200)
        user_data = response.json()["data"]["user"]
        self.assertEqual(user_data["custom_role"], "admin")
        self.assertEqual(user_data["avatar"], "https://example.com/avatar.png")


