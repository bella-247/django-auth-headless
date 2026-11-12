"""Utility functions for user model inspection and attribute retrieval."""


def get_user_email_field(user) -> str:
    """Return the name of the user model's email field."""
    email_getter = getattr(user, "get_email_field_name", None)
    return email_getter() if callable(email_getter) else "email"


def get_user_email(user) -> str:
    """Safely return the user's email or empty string if not present."""
    field_name = get_user_email_field(user)
    return getattr(user, field_name, "") or ""


def get_user_username(user) -> str:
    """Safely return the user's login identifier or empty string."""
    username_getter = getattr(user, "get_username", None)
    return (
        username_getter()
        if callable(username_getter)
        else getattr(user, "username", "")
    )

