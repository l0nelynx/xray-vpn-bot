"""Cross-service query helpers — the single source of truth for DB reads/writes
that more than one service performs.

Each submodule covers one logical area:
- ``repo.system``  — singleton-row helpers (cache version, free-Telemt params)
- ``repo.promos``  — promo lookups and effective-discount resolution
- ``repo.users``   — user lookups and "is paid" predicates
- ``repo.support`` — support ticket / message reads

Contract for every helper:
- First positional arg is an ``AsyncSession``; helpers never open their own.
- Returns ORM objects or primitives; never raw dicts.
- Does not commit. The caller owns the transaction. (The one exception is the
  singleton "get or create" helpers, which need to flush a new row so the
  caller has a usable object on first run.)
"""
from __future__ import annotations
