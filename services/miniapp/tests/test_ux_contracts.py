from services.miniapp.backend.routers.me import _next_onboarding_version
from services.miniapp.backend.routers.payments import _transaction_state


def test_payment_state_waits_for_delivery() -> None:
    assert _transaction_state("created", 0) == "awaiting_payment"
    assert _transaction_state("confirmed", 0) == "processing"
    assert _transaction_state("pending", 0) == "processing"
    assert _transaction_state("confirmed", 1) == "succeeded"
    assert _transaction_state("failed", 0) == "failed"


def test_delivery_success_is_authoritative() -> None:
    assert _transaction_state("failed", 1) == "succeeded"


def test_onboarding_version_never_decreases() -> None:
    assert _next_onboarding_version(None, 1) == 1
    assert _next_onboarding_version(0, 1) == 1
    assert _next_onboarding_version(3, 1) == 3
