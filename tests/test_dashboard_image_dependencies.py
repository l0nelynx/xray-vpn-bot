"""Keep imports used at Dashboard startup present in its runtime image."""
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]


def test_dashboard_image_installs_shared_payments_package() -> None:
    dockerfile = (
        REPO_ROOT / "infra" / "docker" / "dashboard.Dockerfile"
    ).read_text(encoding="utf-8")

    assert "COPY packages/payments /tmp/payments" in dockerfile
    assert "pip install --no-cache-dir /tmp/payments" in dockerfile
