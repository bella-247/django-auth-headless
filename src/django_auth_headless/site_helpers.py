"""Site configuration helpers for django-allauth."""

from django.conf import settings
from django.contrib.sites.models import Site


def get_site() -> Site:
    """Get the current Site record for SITE_ID."""
    return Site.objects.get(pk=settings.SITE_ID)


def ensure_site(domain: str, name: str) -> Site:
    """Create or update the Site record for SITE_ID.

    Args:
        domain: The domain for the site (e.g., "localhost:8000")
        name: The display name for the site

    Returns:
        The created or updated Site instance
    """
    site, _ = Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": domain, "name": name},
    )
    return site