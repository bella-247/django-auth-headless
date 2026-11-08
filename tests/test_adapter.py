from unittest.mock import MagicMock
from django.test import TestCase

from django_auth_headless.adapters import AuthenticationSocialAccountAdapter


class MockUserWithoutEmail:
    pk = 1
    # No email field at all


class MockUserWithCustomEmailField:
    pk = 1
    contact_email = ""

    @classmethod
    def get_email_field_name(cls):
        return "contact_email"


class MockUnsavedUser:
    pk = None
    email = ""


class MockStandardUser:
    pk = 42
    email = ""


class AdapterUserTests(TestCase):
    def setUp(self):
        self.adapter = AuthenticationSocialAccountAdapter()
        self.request = MagicMock()

    def test_pre_social_login_ignores_user_without_email_attribute(self):
        user = MockUserWithoutEmail()
        sociallogin = MagicMock()
        sociallogin.user = user
        sociallogin.account.extra_data = {"email": "provider@example.com"}

        # Should not raise AttributeError
        self.adapter.pre_social_login(self.request, sociallogin)
        self.assertFalse(hasattr(user, "email"))

    def test_pre_social_login_populates_custom_email_field_name(self):
        user = MockUserWithCustomEmailField()
        user.save = MagicMock()
        sociallogin = MagicMock()
        sociallogin.user = user
        sociallogin.account.extra_data = {"email": "custom@example.com"}

        self.adapter.pre_social_login(self.request, sociallogin)
        self.assertEqual(user.contact_email, "custom@example.com")
        user.save.assert_called_once_with(update_fields=["contact_email"])

    def test_pre_social_login_does_not_save_unsaved_user(self):
        user = MockUnsavedUser()
        user.save = MagicMock()
        sociallogin = MagicMock()
        sociallogin.user = user
        sociallogin.account.extra_data = {"email": "unsaved@example.com"}

        self.adapter.pre_social_login(self.request, sociallogin)
        self.assertEqual(user.email, "unsaved@example.com")
        user.save.assert_not_called()

    def test_pre_social_login_populates_and_saves_standard_user(self):
        user = MockStandardUser()
        user.save = MagicMock()
        sociallogin = MagicMock()
        sociallogin.user = user
        sociallogin.account.extra_data = {"email": "standard@example.com"}

        self.adapter.pre_social_login(self.request, sociallogin)
        self.assertEqual(user.email, "standard@example.com")
        user.save.assert_called_once_with(update_fields=["email"])

