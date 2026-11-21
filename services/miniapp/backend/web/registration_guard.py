"""Adaptive registration limits for the single-worker web API."""
from collections import OrderedDict, deque
import hashlib
import hmac
import math
import os
import threading
import time
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from ..config import get_web_allowed_origins, get_web_portal_url

PAIR_WINDOW = 600
PAIR_LIMIT = 6
EMAIL_WINDOW = 3600
FREE_EMAILS = 3
ACTION = "web_register"
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class RegistrationWindow:
    def __init__(self):
        self.lock = threading.Lock()
        self.pairs: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self.emails: OrderedDict[str, dict[str, float]] = OrderedDict()
        self.spent: OrderedDict[bytes, float] = OrderedDict()

    def consume(self, token: str) -> bool:
        """Close the concurrent replay window while Siteverify propagates token use."""
        digest = hashlib.sha256(token.encode()).digest()
        with self.lock:
            now = time.monotonic()
            while self.spent and next(iter(self.spent.values())) <= now - 300:
                self.spent.popitem(last=False)
            if digest in self.spent:
                return False
            self.spent[digest] = now
            return True

    def check(self, ip: str, email: str) -> int:
        """Reserve one attempt atomically. Return seconds until a free email slot."""
        with self.lock:
            now = time.monotonic()
            # Both maps are ordered by last accepted activity. Remove idle IPs
            # and pairs even if those clients never come back.
            while self.pairs and next(iter(self.pairs.values()))[-1] <= now - PAIR_WINDOW:
                self.pairs.popitem(last=False)
            while self.emails and max(next(iter(self.emails.values())).values()) <= now - EMAIL_WINDOW:
                self.emails.popitem(last=False)

            key = (ip, email)
            attempts = self.pairs.setdefault(key, deque())
            while attempts and attempts[0] <= now - PAIR_WINDOW:
                attempts.popleft()
            if len(attempts) >= PAIR_LIMIT:
                raise rate_limited(math.ceil(attempts[0] + PAIR_WINDOW - now))
            attempts.append(now)
            self.pairs.move_to_end(key)

            free = self.emails.setdefault(ip, {})
            for address in list(free):
                if free[address] <= now - EMAIL_WINDOW:
                    del free[address]
            if email not in free and len(free) >= FREE_EMAILS:
                return math.ceil(min(free.values()) + EMAIL_WINDOW - now)
            free[email] = now
            self.emails.move_to_end(ip)
            return 0


window = RegistrationWindow()


def rate_limited(seconds: int) -> HTTPException:
    return HTTPException(429, detail={"code": "rate_limited", "retry_after": seconds},
                         headers={"Retry-After": str(seconds)})


async def enforce(ip: str, email: str, token: str | None) -> None:
    wait = window.check(ip, email)
    if not wait:
        return
    site_key = os.environ.get("TURNSTILE_SITE_KEY")
    secret = os.environ.get("TURNSTILE_SECRET_KEY")
    if not site_key or not secret:
        raise rate_limited(wait)

    # cData binds the proof to the normalized address without disclosing it
    # to the widget provider. IP changes do not invalidate a mobile user's proof.
    binding = hmac.digest(secret.encode(), email.encode(), "sha256").hex()
    challenge = HTTPException(403, detail={
        "code": "challenge_required", "site_key": site_key, "cdata": binding,
    })
    if not token:
        raise challenge
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(VERIFY_URL, data={"secret": secret, "response": token})
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, detail={"code": "challenge_unavailable"}) from exc
    if not isinstance(result, dict) or set(result.get("error-codes") or []) & {
        "internal-error", "invalid-input-secret", "missing-input-secret",
    }:
        raise HTTPException(503, detail={"code": "challenge_unavailable"})
    hosts = {
        urlsplit(origin).hostname
        for origin in [*get_web_allowed_origins(), get_web_portal_url()] if origin
    }
    if (
        result.get("success") is not True
        or result.get("action") != ACTION
        or not result.get("hostname")
        or result["hostname"] not in hosts
        or result.get("cdata") != binding
        or not window.consume(token)
    ):
        raise challenge
