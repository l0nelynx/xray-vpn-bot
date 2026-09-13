import pytest
from pydantic import ValidationError

from services.miniapp.backend.routers.ux import UxEventCreate


@pytest.mark.parametrize("name", [
    "connect_platform_selected", "connect_app_selected", "connect_guide_opened",
    "connect_link_copied", "connect_qr_opened",
])
def test_connect_events_accept_resource_and_device_mode(name: str) -> None:
    event = UxEventCreate(name=name, device_mode="other", resource="subscription")
    assert event.resource == "subscription"
    assert event.device_mode == "other"


def test_resource_field_does_not_accept_personal_links() -> None:
    with pytest.raises(ValidationError):
        UxEventCreate(name="connect_qr_opened", resource="https://example.com/private-subscription")


def test_existing_connect_event_stays_compatible() -> None:
    event = UxEventCreate(name="connect_started", source="home")
    assert event.device_mode is None
    assert event.resource is None
