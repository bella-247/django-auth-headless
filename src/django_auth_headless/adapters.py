"""Custom django-allauth hooks for keeping local user data in sync."""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin


class AuthenticationSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Fill missing local email addresses from the authenticated provider."""

    def pre_social_login(self, request, sociallogin: SocialLogin) -> None:
        user = sociallogin.user
        provider_email = user.email or sociallogin.account.extra_data.get("email", "")

        if not user.email and isinstance(provider_email, str) and provider_email:
            user.email = provider_email
            user.save(update_fields=["email"])

        super().pre_social_login(request, sociallogin)
