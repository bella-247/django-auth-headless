"""PKCE (Proof Key for Code Exchange) utilities adhering strictly to RFC 7636."""

import base64
import hashlib
import re
import secrets

PKCE_UNRESERVED_RE = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")


def is_valid_pkce_string(value: str) -> bool:
    """Validate RFC 7636 unreserved characters and length (43-128 chars)."""
    if not isinstance(value, str):
        return False
    return bool(PKCE_UNRESERVED_RE.match(value))


def verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    """Verify a PKCE code_verifier against a code_challenge (RFC 7636).

    Args:
        code_verifier: The high-entropy random string sent by the client.
        code_challenge: The challenge previously registered by the client.
        method: Transformation method, either "S256" (default) or "plain".

    Returns:
        True if verification succeeds, False otherwise.
    """
    if not isinstance(code_verifier, str) or not isinstance(code_challenge, str):
        return False
    if not code_verifier or not code_challenge:
        return False

    # RFC 7636 requires ASCII unreserved characters
    if not code_verifier.isascii() or not code_challenge.isascii():
        return False

    norm_method = (method or "S256").strip().upper()
    if norm_method == "PLAIN":
        try:
            return secrets.compare_digest(code_verifier, code_challenge)
        except TypeError:
            return False

    if norm_method == "S256":
        try:
            digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
            rfc_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
            return secrets.compare_digest(rfc_challenge, code_challenge.rstrip("="))
        except (TypeError, UnicodeEncodeError):
            return False

    return False
