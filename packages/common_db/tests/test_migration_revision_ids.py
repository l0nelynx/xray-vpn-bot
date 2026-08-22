"""Constraints shared by every Alembic revision in the repository."""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


ALEMBIC_VERSION_NUM_MAX_LENGTH = 32


def test_revision_ids_fit_default_alembic_version_table() -> None:
    """Production uses Alembic's default ``version_num VARCHAR(32)``."""
    root = Path(__file__).resolve().parents[3]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    revisions = ScriptDirectory.from_config(cfg).walk_revisions()

    too_long = sorted(
        revision.revision
        for revision in revisions
        if len(revision.revision) > ALEMBIC_VERSION_NUM_MAX_LENGTH
    )

    assert not too_long, (
        "Alembic revision IDs exceed version_num VARCHAR(32): "
        f"{too_long}"
    )
