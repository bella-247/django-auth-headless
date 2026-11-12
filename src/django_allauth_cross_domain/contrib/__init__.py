"""Framework integration modules for DRF and Django Ninja."""

__all__ = [
    "BearerTokenAuthentication",
    "BearerAuth",
]


def __getattr__(name: str):
    if name == "BearerTokenAuthentication":
        from .rest_framework import BearerTokenAuthentication

        return BearerTokenAuthentication
    if name == "BearerAuth":
        from .ninja import BearerAuth

        return BearerAuth
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
