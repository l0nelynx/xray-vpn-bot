import json
from pathlib import Path
import sqlite3
import tarfile
import zipfile

import pytest

from scripts import deployment_backup as backup


@pytest.mark.parametrize("host", ["postgres", "xray-postgres", "db-alias"])
@pytest.mark.parametrize("password", ["a#b", "a/b", "a?b", "a[b", "encoded%40value"])
def test_local_postgres_url(host, password):
    client = {"networks": {"data": {}}}
    postgres = {"container_name": "xray-postgres", "networks": {"data": {"aliases": ["db-alias"]}}}
    url = f"postgresql+asyncpg://app:{password}@{host}:5432/shop"
    backup.check_postgres_url("miniapp", url, client, postgres)


@pytest.mark.parametrize("endpoint", [
    "elsewhere.example/shop", "elsewhere.example/shop@postgres", "elsewhere@postgres/shop",
    "postgres/shop?host=elsewhere.example", "other-network-alias/shop", "[invalid/shop",
])
def test_unverified_database_remains_blocked_without_logging_credentials(endpoint):
    url = f"postgresql+asyncpg://app:sensitive#value@{endpoint}"
    postgres = {"networks": {"private": {"aliases": ["other-network-alias"]}}}
    with pytest.raises(ValueError, match="miniapp:") as error:
        backup.check_postgres_url("miniapp", url, {"networks": {"data": {}}}, postgres)
    assert "sensitive" not in str(error.value)


@pytest.mark.parametrize("previous_rdb", [None, b"previous disk state"])
def test_backup_restores_project_and_starts_saved_images(tmp_path, monkeypatch, previous_rdb):
    source = tmp_path / "deployed"
    source.mkdir()
    files = {
        ".env": b"POSTGRES_PASSWORD=fixture\n",
        "config.yml": b"token: fixture\n",
        "docker-compose.yml": b"services: {}\n",
        "pg_data/PG_VERSION": b"16\n",
        "pg_data/base/42/17003": bytes(range(256)),
        "fcm-sa.json": b'{"project_id":"test"}',
        "support_uploads/3/photo.png": b"attachment",
        ".local/other-settings": b"untracked",
    }
    for name, data in files.items():
        path = source / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(data)
    (source / "db").mkdir()
    with sqlite3.connect(source / "db/support_bot.sqlite3") as db:
        db.execute("create table tickets(id integer)")
        db.execute("insert into tickets values (17)")
    db.close()
    (source / "redis_data").mkdir()
    if previous_rdb:
        (source / "redis_data/dump.rdb").write_bytes(previous_rdb)
    archive = tmp_path / "backup.zip"
    runtime = tmp_path / "test-runtime.tar.gz"
    runtime.write_bytes(b"runtime fixture")
    monkeypatch.setenv("XRAY_BACKUP_RUNTIME", str(runtime))
    restored = tmp_path / "restored"
    active = {"redis": "r", "postgres": "p", "bot": "b"}
    manifest = {"format": 1, "project": "shop", "files": ["docker-compose.yml"],
                "active": list(active), "architecture": "x86_64", "volatile_redis": True,
                "images": {s: "sha256:" + c * 64 for s, c in (("redis", "a"), ("postgres", "b"),
                                                                ("bot", "c"), ("migrate", "c"))}}
    monkeypatch.setattr(backup, "inventory", lambda root: (["docker", "compose"], active, manifest))
    monkeypatch.setattr(backup, "containers", lambda *args: [])
    calls = []

    def run(*args):
        calls.append(args)
        if args[1:3] == ("image", "save"):
            Path(args[4]).write_bytes(b"image fixture")
        if args[1:3] == ("image", "load"):
            assert Path(args[4]).read_bytes() == b"image fixture"
        if "up" in args and args[-1] == "redis":
            assert (restored / "redis_data/dump.rdb").read_bytes() == b"queued jobs"

    def output(*args):
        if args[-1] == "SAVE":
            rdb = source / "redis_data/temp.rdb"
            rdb.write_bytes(b"queued jobs")
            rdb.replace(rdb.with_name("dump.rdb"))
            return "OK"
        if "{{json .State}}" in args:
            return '{"Running": false, "ExitCode": 0}'
        if "{{.State.Health.Status}}" in args:
            return "healthy"
        if args[1] == "info":
            return "x86_64"
        if "config" in args:
            return json.dumps({"services": {s: {} for s in manifest["images"]},
                               "networks": {"edge": {"name": "edge", "external": True}}})
        if "ls" in args or "ps" in args:
            return ""
        pytest.fail(f"Unexpected Docker command {args}")

    monkeypatch.setattr(backup, "run", run)
    monkeypatch.setattr(backup, "output", output)
    backup.backup(source, archive)
    assert ("docker", "start", "b") in calls
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert "deployment_backup.py" in bundle.namelist()
        assert bundle.read("backup.sh") == (Path(backup.__file__).resolve().parent.parent / "backup.sh").read_bytes()
        assert bundle.read("runtime/test-runtime.tar.gz") == runtime.read_bytes()
    backup.restore(archive, restored)
    for name, data in files.items():
        assert (restored / name).read_bytes() == data
    for root in (source, restored):
        rdb = root / "redis_data/dump.rdb"
        assert (rdb.read_bytes() if rdb.exists() else None) == previous_rdb
        assert not (rdb.parent / backup.PREVIOUS_RDB).exists()
    with sqlite3.connect(restored / "db/support_bot.sqlite3") as db:
        assert db.execute("select id from tickets").fetchone() == (17,)
    db.close()
    images = json.loads((restored / backup.IMAGE_OVERRIDE).read_text())["services"]
    assert images["bot"] == images["migrate"] == {"image": "xray-recovery:" + "c" * 64}
    assert ("docker", "network", "create", "edge") in calls
    assert calls[-1][-3:] == tuple(active)
    assert "--wait" in calls[-1]
    with pytest.raises(ValueError, match="new directory"):
        backup.restore(archive, restored)
    with pytest.raises(ValueError, match="new archive"):
        backup.backup(source, archive)


def test_snapshot_failure_restarts_original_services(monkeypatch):
    calls = []
    monkeypatch.setattr(backup, "run", lambda *args: calls.append(args))
    monkeypatch.setattr(backup, "wait_healthy", lambda ids: None)
    monkeypatch.setattr(backup, "output", lambda *args: "ERR disk full")
    with pytest.raises(RuntimeError, match="Redis SAVE"):
        with backup.stopped_for_snapshot(["docker", "compose"], {"bot": "b", "postgres": "p", "redis": "r"}, None):
            pytest.fail("Snapshot must not start after SAVE failed")
    assert calls == [("docker", "compose", "stop", "-t", "120", "bot"),
                     ("docker", "start", "p", "r"), ("docker", "start", "b")]


def test_damaged_project_never_starts_containers(tmp_path, monkeypatch):
    archive = tmp_path / "broken.zip"
    root = tmp_path / "restore"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps({"format": 1, "project": "shop", "architecture": "x86_64"}))
        bundle.writestr("project.tar", b"truncated")
    monkeypatch.setattr(backup, "output", lambda *args: "x86_64")
    monkeypatch.setattr(backup, "containers", lambda *args: [])
    monkeypatch.setattr(backup, "run", lambda *args: pytest.fail("Docker state changed"))
    with pytest.raises(tarfile.ReadError):
        backup.restore(archive, root)
    assert not root.exists()
