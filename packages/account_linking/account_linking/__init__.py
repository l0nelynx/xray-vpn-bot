"""Shared Android<->Telegram account merge logic.

The seller bot (`app.handlers.android_link`) and the miniapp
(`miniapp.backend.android.link_router`) used to carry byte-identical copies of
this module. It is self-contained against the shared packages only — it takes a
SQLAlchemy ``session`` from the caller, reads ORM models from ``common_db`` and
looks users up via ``remnawave_client.api`` — so it lives here as the single
source of truth.

Both public entry points (``merge_android_and_tg``, ``merge_tg_into_email``,
``import_subscription_by_uuid``)
and the helpers/exceptions the tests exercise are re-exported here so callers can
``from account_linking import ...``.
"""
from .merge import (
    LookupNotFound,
    MergeBlocked,
    _apply_merge_db,
    _classify,
    _copy_if_empty,
    _decide,
    _lookup_a_side_rw,
    _lookup_rw,
    import_subscription_by_uuid,
    merge_android_and_tg,
    merge_tg_into_email,
)

__all__ = [
    "LookupNotFound",
    "MergeBlocked",
    "import_subscription_by_uuid",
    "merge_android_and_tg",
    "merge_tg_into_email",
    # Helpers/exceptions exported for the test-suite and advanced callers.
    "_apply_merge_db",
    "_classify",
    "_copy_if_empty",
    "_decide",
    "_lookup_a_side_rw",
    "_lookup_rw",
]
