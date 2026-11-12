"""Framework integration modules for DRF and Django Ninja."""

from .ninja import BearerAuth
from .rest_framework import BearerTokenAuthentication

__all__ = [
    "BearerTokenAuthentication",
    "BearerAuth",
]

