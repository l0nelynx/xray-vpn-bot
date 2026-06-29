import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .config import (
    INSECURE_DASHBOARD_SECRET,
    get_dashboard_login,
    get_dashboard_password,
    get_secret_key,
)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
# HS256 keys shorter than the 256-bit hash output are weaker than the algorithm
# (RFC 7518 §3.2). Refuse anything below this.
MIN_SECRET_BYTES = 32

security = HTTPBearer()


def validate_security_config() -> None:
    """Fail-closed startup checks. Raises RuntimeError to abort boot when the
    dashboard is configured with insecure defaults.

    The admin panel is internet-facing; with a known/weak ``dashboard_secret``
    anyone can forge an admin JWT (``create_access_token("admin")``) without the
    password, so we refuse to start rather than serve a forgeable panel.
    """
    secret = get_secret_key()
    if not secret:
        raise RuntimeError(
            "dashboard_secret is not set — add a strong random value "
            f"(>= {MIN_SECRET_BYTES} bytes) to config.yml"
        )
    if secret == INSECURE_DASHBOARD_SECRET:
        raise RuntimeError(
            "dashboard_secret still uses the built-in insecure default — "
            "change it in config.yml (e.g. `openssl rand -hex 32`)"
        )
    if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
        raise RuntimeError(
            f"dashboard_secret must be at least {MIN_SECRET_BYTES} bytes (HS256)"
        )

    password = get_dashboard_password()
    if not password or password == "admin":
        raise RuntimeError(
            "dashboard_password is unset or the default 'admin' — "
            "set a strong password in config.yml"
        )


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def verify_credentials(login: str, password: str) -> bool:
    """Constant-time credential check. Both comparisons always run so the
    response time does not leak which field (or how many leading chars) matched."""
    login_ok = hmac.compare_digest(
        login.encode("utf-8"), get_dashboard_login().encode("utf-8")
    )
    password_ok = hmac.compare_digest(
        password.encode("utf-8"), get_dashboard_password().encode("utf-8")
    )
    return login_ok and password_ok


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
        subject: str = payload.get("sub")
        if subject is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return subject
    except jwt.InvalidTokenError:
        # Covers bad signature, malformed token, and expiry
        # (ExpiredSignatureError subclasses InvalidTokenError).
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
