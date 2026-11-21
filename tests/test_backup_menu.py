"""Exercise the Bash launcher with a local runtime fixture, independent of Docker or root."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile

import pytest


LAUNCHER = Path(__file__).resolve().parents[1] / "backup.sh"
ASSET = "cpython-3.13.18+20261110-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
BASH = shutil.which("bash") if os.name != "nt" else shutil.which(
    "bash.exe", path=str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin")
)
pytestmark = pytest.mark.skipif(not BASH, reason="Bash required")


def menu(root, answers):
    return subprocess.run(
        [BASH, "-c", 'export PATH="$PWD/tools:$PATH" XDG_CACHE_HOME="$PWD/cache"; exec bash backup.sh'],
        cwd=root, input=answers.encode(), capture_output=True, timeout=20,
    )


def test_exit_and_invalid_choice(tmp_path):
    shutil.copyfile(LAUNCHER, tmp_path / "backup.sh")
    result = menu(tmp_path, "?\n0\n")
    assert result.returncode == 0
    assert all(s in result.stdout.decode() for s in ("Create a backup", "Restore from a backup", "Exit", "Enter 1, 2, or 0."))
    assert not (tmp_path / "cache").exists()


def test_download_then_offline_restore_without_checkout(tmp_path):
    # Replace only the pinned digest so the launcher verifies and extracts a tiny executable fixture.
    interpreter = b'#!/bin/sh\nprintf "%s\\n" "$@" > invocation\ncat "$2" > invoked-engine\n'
    asset = tmp_path / ASSET
    with tarfile.open(asset, "w:gz") as tar:
        executable = tarfile.TarInfo("python/bin/python3")
        executable.mode = 0o755
        executable.size = len(interpreter)
        tar.addfile(executable, io.BytesIO(interpreter))
    launcher = LAUNCHER.read_text().replace(
        "f2d2199eb25880e07863b391cf7124e7ffa1338b0d65600dfcec117c4223a7fb",
        hashlib.sha256(asset.read_bytes()).hexdigest(),
    )
    (tmp_path / "backup.sh").write_text(launcher, newline="\n")
    tools = tmp_path / "tools"
    tools.mkdir()
    for name, body in {
        "uname": 'if [ "$1" = -s ]; then echo Linux; else echo x86_64; fi',
        "getconf": "exit 0",
        "id": "echo 0",
        "docker": '[ "$*" = "compose version" ]',
        "curl": 'while [ "$1" != --output ]; do shift; done; cp ./*.tar.gz "$2"',
    }.items():
        stub = tools / name
        stub.write_text("#!/bin/sh\n" + body + "\n", newline="\n")
        stub.chmod(0o755)
    engine = tmp_path / "scripts/deployment_backup.py"
    engine.parent.mkdir()
    engine.write_bytes(b"project engine")
    result = menu(tmp_path, "1\nmy backup.zip\n")
    assert result.returncode == 0, result.stderr
    invocation = (tmp_path / "invocation").read_text().splitlines()
    assert invocation[2:5] == ["backup", "my backup.zip", "--project-dir"]
    assert (tmp_path / "invoked-engine").read_bytes() == b"project engine"

    engine.unlink()
    shutil.rmtree(tmp_path / "cache")
    asset_bytes = asset.read_bytes()
    asset.unlink()  # Any attempt to download via the curl stub now fails.
    archive = tmp_path / "my backup.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("deployment_backup.py", b"embedded engine")
        bundle.writestr("runtime/" + ASSET, asset_bytes)
    result = menu(tmp_path, "2\n\nnew project\n")
    assert result.returncode == 0, result.stderr
    invocation = (tmp_path / "invocation").read_text().splitlines()
    assert invocation[2] == "restore" and invocation[3].endswith("/my backup.zip")
    assert invocation[4] == "new project"
    assert (tmp_path / "invoked-engine").read_bytes() == b"embedded engine"
