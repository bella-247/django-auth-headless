from django.conf import settings
from django.utils.module_loading import import_string

from allauth.socialaccount.models import SocialAccount

from .utils import get_user_email, get_user_username

def default_user_serializer(user) -> dict:
    """Safely extract core user profile information and connected OAuth providers."""
    email = get_user_email(user)

    if not email:
        provider_account = (
            SocialAccount.objects.filter(user=user)
            .exclude(extra_data__email="")
            .first() 
        )
        if provider_account:
            email = provider_account.extra_data.get("email", "")

    connected_providers = list(
        SocialAccount.objects.filter(user=user)
        .values_list("provider", flat=True)
        .distinct()
    )

    return {
        "id": user.pk,
        "username": get_user_username(user),
        "email": email,
        "connected_providers": connected_providers,
    }


def get_user_payload(user) -> dict:
    """Return serialized user data using custom serializer if configured, or default."""
    serializer_setting = getattr(settings, "DJANGO_AUTH_USER_SERIALIZER", None)
    if serializer_setting:
        if isinstance(serializer_setting, str):
            serializer = import_string(serializer_setting)
        else:
            serializer = serializer_setting
        return serializer(user)

    return default_user_serializer(user)
