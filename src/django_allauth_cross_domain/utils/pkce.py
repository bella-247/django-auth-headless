"""PKCE (Proof Key for Code Exchange) utilities adhering to RFC 7636."""

import base64
import hashlib
import secrets


def verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    """Verify a PKCE code_verifier against a code_challenge (RFC 7636).

    Args:
        code_verifier: The high-entropy cryptographic random string sent by the client.
        code_challenge: The challenge previously registered by the client.
        method: Transformation method, either "S256" (default) or "plain".

    Returns:
        True if verification succeeds, False otherwise.
    """
    if not isinstance(code_verifier, str) or not isinstance(code_challenge, str):
        return False
    if not code_verifier or not code_challenge:
        return False

    norm_method = (method or "S256").strip().upper()
    if norm_method == "PLAIN":
        return secrets.compare_digest(code_verifier, code_challenge)

    if norm_method == "S256":
        # Standard RFC 7636: BASE64URL-ENCODE(SHA256(ASCII(code_verifier))) without padding
        digest = hashlib.sha256(code_verifier.encode("ascii", errors="ignore")).digest()
        rfc_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        if secrets.compare_digest(rfc_challenge, code_challenge.rstrip("=")):
            return True
        # Support hex SHA-256 fallback for non-base64 client implementations
        hex_challenge = hashlib.sha256(code_verifier.encode("ascii", errors="ignore")).hexdigest()
        if secrets.compare_digest(hex_challenge, code_challenge):
            return True

    return False

