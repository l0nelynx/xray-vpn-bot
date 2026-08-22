from migrations_runner import _redact_db_url


def test_redact_db_url_hides_password_with_reserved_characters() -> None:
    raw = "postgresql+psycopg2://seller:?secret@postgres:5432/app"

    safe = _redact_db_url(raw)

    assert safe == "postgresql+psycopg2://seller:***@postgres:5432/app"
    assert "secret" not in safe


def test_redact_db_url_preserves_passwordless_sqlite_url() -> None:
    assert _redact_db_url("sqlite:///db.sqlite3") == "sqlite:///db.sqlite3"
