"""Reject disposable / probe emails at registration time."""
from __future__ import annotations

import re

from fastapi import HTTPException, status

from ..config import get_email_denied_domains

# RFC / lab domains plus known probe TLDs from spam registrations.
_DEFAULT_DENIED_DOMAINS: frozenset[str] = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "localhost",
        "invalid",
        "qzz.io",
    }
)

# Local-part patterns that only match obvious probes (not `test@gmail.com`).
_DENIED_LOCAL_RE = re.compile(r"^(?:probe\d+|test[_-].+)$", re.IGNORECASE)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def denied_domains() -> frozenset[str]:
    extra = get_email_denied_domains()
    if not extra:
        return _DEFAULT_DENIED_DOMAINS
    return _DEFAULT_DENIED_DOMAINS | frozenset(extra)


def is_email_denied(email: str) -> bool:
    normalized = normalize_email(email)
    if "@" not in normalized:
        return True
    local, _, domain = normalized.partition("@")
    if not local or not domain:
        return True
    if domain in denied_domains():
        return True
    # Also block subdomains of denied roots (e.g. mail.example.com).
    for denied in denied_domains():
        if domain == denied or domain.endswith("." + denied):
            return True
    if _DENIED_LOCAL_RE.match(local):
        return True
    return False


def assert_email_allowed(email: str) -> str:
    """Return normalized email or raise 403 ``email_rejected``."""
    normalized = normalize_email(email)
    if is_email_denied(normalized):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "email_rejected"},
        )
    return normalized
