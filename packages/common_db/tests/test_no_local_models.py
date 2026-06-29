"""Step 6 drift guards — no ORM declarations outside `common_db`.

The whole point of unifying on `common_db.Base` is that there's exactly
one mapped class per table. These guards catch the regressions that
would silently re-fork the schema:

  1. `class X(Base): __tablename__ = ...` anywhere outside common_db.
     If this slips through, two classes register the same table, alembic
     autogenerate produces a meaningless diff, and Postgres FK semantics
     start depending on import order.

  2. `class _ ( DeclarativeBase , … )` anywhere outside common_db.
     Someone re-rolling the Base pattern instead of `from common_db
     import Base` would create a *second* metadata registry — every
     table on it would be invisible to alembic and to the shims.

Both checks are pure AST passes; they need no DB and no SQLAlchemy import,
so they run in <50ms even across the full tree.

When this test fails:
  - If you added a new shared model: define it in `common_db/models/`
    and re-export it from the existing shims.
  - If you have a one-off table for a *truly* isolated service (e.g. the
    legacy `support.py` standalone bot): keep it in a separate process,
    its own DB file/schema, AND outside the directories scanned below.

Skipped when the repo layout cannot be located (e.g. the test package is
installed standalone without the source tree).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


# Resolve repo root by walking up from this file:
# packages/common_db/tests/test_no_local_models.py  -> parents[3] = repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

# Directories whose Python sources must NOT declare ORM-mapped classes
# nor invent a new DeclarativeBase. New entries: any first-party service
# that imports from common_db.
SCANNED_DIRS = ("app", "dashboard", "miniapp")

# Files that are explicitly allowed to mention the forbidden symbols
# even though they live inside SCANNED_DIRS. Use sparingly — every entry
# is a hole in the guard.
EXEMPT_FILES: frozenset[str] = frozenset({
    # (none currently — the shims re-export from common_db, they don't
    # use DeclarativeBase or define `class X(Base)` themselves.)
})

# Symbol names that, when used as a class base, indicate a SQLAlchemy
# declarative root. Hitting any of these outside common_db is a bug.
FORBIDDEN_BASE_SYMBOLS: frozenset[str] = frozenset({"DeclarativeBase", "DeclarativeBaseNoMeta"})


def _iter_python_files() -> list[Path]:
    if not REPO_ROOT.is_dir():
        pytest.skip(f"repo root not found at {REPO_ROOT}")
    files: list[Path] = []
    for top in SCANNED_DIRS:
        root = REPO_ROOT / top
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            # Skip generated/cache + virtualenv-style nesting just in case
            parts = set(path.parts)
            if "__pycache__" in parts or ".venv" in parts or "node_modules" in parts:
                continue
            files.append(path)
    return files


def _class_bases(node: ast.ClassDef) -> list[str]:
    """Return the *named* base classes as flat strings.

    Handles `Base`, `pkg.Base`, `AsyncAttrs`. Star/subscript bases are
    rare in ORM code and return their dotted form for inspection.
    """
    out: list[str] = []
    for b in node.bases:
        # plain name: class X(Base) -> "Base"
        if isinstance(b, ast.Name):
            out.append(b.id)
        # attribute: class X(common_db.Base) -> "common_db.Base" (tail = "Base")
        elif isinstance(b, ast.Attribute):
            parts: list[str] = []
            cur: ast.AST = b
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            out.append(".".join(reversed(parts)))
        else:
            out.append(ast.unparse(b))
    return out


def test_no_local_orm_classes_outside_common_db() -> None:
    """No `class X(Base): __tablename__ = ...` outside common_db.

    Heuristic: a class whose base list mentions a bare `Base` AND whose
    body assigns `__tablename__` is, with overwhelming probability, an
    ORM table declaration. We don't import Base — we just look at the
    syntax — so dashboard shims that re-export Base are safe.
    """
    offenders: list[str] = []
    for f in _iter_python_files():
        if f.name in EXEMPT_FILES:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = _class_bases(node)
            # Looks like an ORM class if a base named "Base" appears AND
            # the body declares __tablename__.
            base_names = {b.split(".")[-1] for b in bases}
            if "Base" not in base_names:
                continue
            has_tablename = any(
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "__tablename__"
                for stmt in node.body
            )
            if has_tablename:
                rel = f.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{node.lineno}: class {node.name}({', '.join(bases)})")

    assert not offenders, (
        "ORM-mapped classes found outside packages/common_db/. Move them into "
        "common_db/models/ and re-export from the appropriate shim:\n  "
        + "\n  ".join(offenders)
    )


def test_no_declarative_base_outside_common_db() -> None:
    """No `class _(DeclarativeBase, …)` outside common_db.

    Catches the subtler regression: someone re-rolls `class Base(...)`
    in a service module. Even if no model attaches to it, the temptation
    will, and at that point we'd have two metadata registries silently
    fighting over the same table names. The fix is always
    `from common_db import Base`.
    """
    offenders: list[str] = []
    for f in _iter_python_files():
        if f.name in EXEMPT_FILES:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_tails = {b.split(".")[-1] for b in _class_bases(node)}
            hit = FORBIDDEN_BASE_SYMBOLS & base_tails
            if hit:
                rel = f.relative_to(REPO_ROOT)
                offenders.append(
                    f"{rel}:{node.lineno}: class {node.name} extends "
                    f"{sorted(hit)} — import Base from common_db instead"
                )

    assert not offenders, (
        "DeclarativeBase usage found outside packages/common_db/. "
        "Use `from common_db import Base` and subclass that single Base:\n  "
        + "\n  ".join(offenders)
    )


def test_drift_guard_actually_scans_files() -> None:
    """Cheap sanity check: if SCANNED_DIRS suddenly find nothing the
    guards above pass vacuously, which would be much worse than a
    failing test. Force them to look at *something*."""
    files = _iter_python_files()
    assert len(files) > 50, (
        f"drift guard only saw {len(files)} files under {SCANNED_DIRS} — "
        "did the repo layout change?"
    )
