"""Optional host-service observer; never changes existing client error behavior."""
import logging
from typing import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)
_observer: Callable[[], Awaitable[None]] | None = None


def set_failure_observer(observer: Callable[[], Awaitable[None]] | None) -> None:
    global _observer
    _observer = observer


def is_availability_error(exc: Exception) -> bool:
    from .client import _http_status_code

    code = _http_status_code(exc)
    # Missing users, validation errors and per-request rate limits are not outages.
    # The SDK also represents transport failures as ApiError(status_code=0).
    return isinstance(exc, (httpx.TransportError, TimeoutError)) or code in {0, 401, 403, 408} or (code is not None and code >= 500)


async def report_failure(exc: Exception) -> None:
    if _observer is not None and is_availability_error(exc):
        try:
            await _observer()
        except Exception:
            # Reporting must not mask the original error or break delivery flows.
            logger.exception("Failed to record Remnawave unavailability")
