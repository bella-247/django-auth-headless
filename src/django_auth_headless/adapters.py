"""Custom django-allauth hooks for keeping local user data in sync."""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin

from .utils import get_user_email_field

class AuthenticationSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Fill missing local email addresses from the authenticated provider."""

    def pre_social_login(self, request, sociallogin: SocialLogin) -> None:
        user = sociallogin.user
        email_field = get_user_email_field(user)

        if hasattr(user, email_field):
            current_email = getattr(user, email_field, "")
            extra_data = (
                getattr(getattr(sociallogin, "account", None), "extra_data", {}) or {}
            )
            provider_email = current_email or extra_data.get("email", "")

            if not current_email and isinstance(provider_email, str) and provider_email:
                setattr(user, email_field, provider_email)
                if getattr(user, "pk", None) is not None:
                    try:
                        user.save(update_fields=[email_field])
                    except Exception:
                        pass

        super().pre_social_login(request, sociallogin)
