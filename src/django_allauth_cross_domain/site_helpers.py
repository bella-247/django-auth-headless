"""Site configuration helpers for django-allauth."""

from django.conf import settings
from django.contrib.sites.models import Site


def get_site() -> Site:
    """Get the current Site record for SITE_ID."""
    site_id = getattr(settings, "SITE_ID", 1)
    return Site.objects.get(pk=site_id)


def ensure_site(domain: str, name: str) -> Site:
    """Create or update the Site record for SITE_ID.

    Args:
        domain: The domain for the site (e.g., "localhost:8000")
        name: The display name for the site

    Returns:
        The created or updated Site instance
    """
    site_id = getattr(settings, "SITE_ID", 1)
    site, _ = Site.objects.update_or_create(
        pk=site_id,
        defaults={"domain": domain, "name": name},
    )
    return site
