#!/usr/bin/env python3
"""Back up or restore the Linux Docker Compose deployment. Run with --help."""

import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
import zipfile


IMAGE_OVERRIDE = ".xray-recovery-images.json"
PREVIOUS_RDB = ".xray-before-backup.rdb"
LABEL = "com.docker.compose."


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def run(*args):
    subprocess.run(args, check=True)


def compose(root, project, files):
    args = ["docker", "compose", "--project-directory", str(root), "-p", project]
    for file in files:
        args.extend(["-f", str(root / file)])
    return args


def containers(*filters):
    args = ["docker", "ps", "-aq"]
    for item in filters:
        args.extend(["--filter", item])
    ids = output(*args).split()
    return json.loads(output("docker", "inspect", *ids)) if ids else []


def service_name(container):
    return container["Config"]["Labels"][LABEL + "service"]


def check_postgres_url(service, url, client, postgres):
    # Match SQLAlchemy's userinfo grammar first. It allows /, ? and # in
    # passwords, while urlsplit treats them as the end of the authority.
    scheme, separator, rest = url.partition("://")
    if not separator or scheme.partition("+")[0] not in {"postgres", "postgresql"}:
        raise ValueError(f"{service}: DATABASE_URL must use the project's PostgreSQL cluster for this backup")
    endpoint = re.sub(r"^[^:/]*(?::[^@]*)?@", "", rest, count=1)
    try:
        address = urlsplit("//" + endpoint, allow_fragments=False)
        host = address.hostname
    except ValueError:
        raise ValueError(f"{service}: cannot parse the PostgreSQL host in DATABASE_URL") from None
    if not host or "@" in address.netloc:
        raise ValueError(f"{service}: cannot identify the PostgreSQL host in DATABASE_URL")
    if {"host", "hostaddr", "service"} & parse_qs(address.query, keep_blank_values=True).keys():
        raise ValueError(f"{service}: DATABASE_URL overrides the PostgreSQL endpoint in its query; "
                         "use the Compose PostgreSQL hostname in the URL authority")

    networks = postgres.get("networks", {})
    names = {"postgres"}
    if postgres.get("container_name"):
        names.add(postgres["container_name"])
    for network in networks.keys() & client.get("networks", {}).keys():
        names.update((networks[network] or {}).get("aliases") or [])
    if host.rstrip(".").lower() not in {name.lower() for name in names}:
        raise ValueError(f"{service}: DATABASE_URL does not match the Compose PostgreSQL container "
                         f"(expected one of {', '.join(sorted(names))}). This backup covers its pg_data directory.")


def inventory(root):
    matches = containers("label=" + LABEL + "service=postgres",
                         "label=" + LABEL + "project.working_dir=" + str(root))
    if len(matches) != 1:
        raise ValueError("Expected one deployed postgres container for " + str(root))
    labels = matches[0]["Config"]["Labels"]
    project = labels[LABEL + "project"]
    files = [str(Path(f).resolve().relative_to(root))
             for f in labels[LABEL + "project.config_files"].split(",")]
    cmd = compose(root, project, files)
    config = json.loads(output(*cmd, "config", "--no-path-resolution", "--format", "json"))
    members = containers("label=" + LABEL + "project=" + project)
    active = {}
    images = {}
    data_mounts = {"postgres": ("/var/lib/postgresql/data", root / "pg_data"),
                   "redis": ("/data", root / "redis_data")}
    for container in members:
        service = service_name(container)
        state = container["State"]
        if container["Config"]["Labels"].get(LABEL + "oneoff", "").lower() == "true":
            if state["Running"]:
                raise ValueError("Finish the one-off container first: " + container["Name"])
            continue
        if service not in config["services"] or service in images:
            raise ValueError("Unexpected or replicated Compose service: " + service)
        images[service] = container["Image"]
        if state["Paused"] or state["Restarting"]:
            raise ValueError("Unstable service: " + service)
        if state["Running"]:
            active[service] = container["Id"]
        binds = {}
        for mount in container["Mounts"]:
            if mount["Type"] != "bind" or not Path(mount["Source"]).resolve().is_relative_to(root):
                raise ValueError(f"{service}: mount outside the project snapshot: {mount['Destination']}")
            binds[mount["Destination"]] = Path(mount["Source"]).resolve()
        if service in data_mounts:
            target, expected = data_mounts[service]
            if binds.get(target) != expected.resolve():
                raise ValueError(f"{service}: expected {expected} mounted at {target}")
        model = config["services"][service]
        for mount in model.get("volumes", []):
            source = Path(mount.get("source", ""))
            if mount["type"] != "bind" or source.is_absolute():
                raise ValueError(f"{service}: use a project-relative bind mount at {mount['target']}")
            if binds.get(mount["target"]) != (root / source).resolve():
                raise ValueError(f"{service}: deployed mount differs from Compose at {mount['target']}")
        env = dict(v.split("=", 1) for v in container["Config"]["Env"] if "=" in v)
        # Compose doubles literal dollar signs when serializing the resolved model.
        if any(v is not None and env.get(k) not in (v, v.replace("$$", "$"))
               for k, v in model.get("environment", {}).items()):
            raise ValueError(f"{service}: deployed environment differs from the Compose configuration")
        if env.get("REDIS_URL") and urlsplit(env["REDIS_URL"]).hostname != "redis":
            raise ValueError(f"{service}: external Redis needs its own backup")
        if env.get("DATABASE_URL"):
            check_postgres_url(service, env["DATABASE_URL"], model, config["services"]["postgres"])
    if not {"postgres", "redis"} <= active.keys() or "migrate" in active:
        raise ValueError("Postgres and Redis must be running and migrations must be finished")
    # A completed migration container can have been removed after deployment.
    needed = set(active)
    pending = list(active)
    while pending:
        deps = config["services"][pending.pop()].get("depends_on", {}).keys() - needed
        needed.update(deps)
        pending.extend(deps)
    by_ref = {config["services"][s]["image"]: images[s] for s in active}
    for service in needed - images.keys():
        ref = config["services"][service]["image"]
        images[service] = by_ref.get(ref) or output("docker", "image", "inspect", "-f", "{{.Id}}", ref)
    redis_cli = ["docker", "exec", active["redis"], "redis-cli", "-e", "--raw", "CONFIG", "GET"]
    volatile_redis = output(*redis_cli, "save") == "save" and output(*redis_cli, "appendonly") == "appendonly\nno"
    return cmd, active, {
        "format": 1, "project": project, "files": files, "active": list(active),
        "images": {s: images[s] for s in sorted(needed)},
        "volatile_redis": volatile_redis,
        "architecture": output("docker", "info", "-f", "{{.Architecture}}"),
    }


def wait_healthy(ids):
    deadline = time.monotonic() + 120
    for container in ids:
        while output("docker", "inspect", "-f", "{{.State.Health.Status}}", container) != "healthy":
            if time.monotonic() >= deadline:
                raise RuntimeError("Timed out waiting for healthy database container " + container[:12])
            time.sleep(1)


def finish_redis_boot(directory):
    # With persistence disabled a leftover recovery RDB would replay old jobs
    # on every future Redis restart. Restore the original on-disk state.
    original = directory / PREVIOUS_RDB
    dump = directory / "dump.rdb"
    if original.exists():
        os.replace(original, dump)
        original.unlink(missing_ok=True)  # SAVE may have failed before replacing the inode.
    else:
        dump.unlink(missing_ok=True)


@contextlib.contextmanager
def stopped_for_snapshot(cmd, active, volatile_dir):
    databases = ["postgres", "redis"]
    apps = [s for s in active if s not in databases]
    if volatile_dir is not None:
        original = volatile_dir / PREVIOUS_RDB
        if os.path.lexists(original):
            raise ValueError("Previous Redis snapshot still needs attention: " + str(original))
        dump = volatile_dir / "dump.rdb"
        if dump.exists():
            os.link(dump, original)
    try:
        if apps:
            run(*cmd, "stop", "-t", "120", *apps)
        if output("docker", "exec", active["redis"], "redis-cli", "--raw", "SAVE") != "OK":
            raise RuntimeError("Redis SAVE failed")
        run(*cmd, "stop", "-t", "120", *databases)
        for service, cid in active.items():
            state = json.loads(output("docker", "inspect", "-f", "{{json .State}}", cid))
            if state["Running"] or (service in databases and state["ExitCode"] != 0):
                raise RuntimeError("Service did not shut down cleanly: " + service)
        yield
    finally:
        ids = [active[s] for s in databases]
        try:
            run("docker", "start", *ids)
            wait_healthy(ids)
            if volatile_dir is not None:
                finish_redis_boot(volatile_dir)
        finally:
            if apps:
                run("docker", "start", *(active[s] for s in apps))


def project_snapshot(root, destination):
    def check_link(member):
        if member.issym():
            link = Path(member.linkname)
            if link.is_absolute() or not (root / member.name).resolve().is_relative_to(root):
                raise ValueError("Non-portable project symlink: " + member.name)
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError("Unsupported project file: " + member.name)
        return member

    with tarfile.open(destination, "w") as tar:
        tar.add(root, arcname=".", filter=check_link)


def backup(root, archive):
    if archive.is_relative_to(root) or archive.exists():
        raise ValueError("Choose a new archive path outside the project")
    for name in (".env", "config.yml", "pg_data/PG_VERSION"):
        if not (root / name).is_file():
            raise ValueError("Missing deployment file: " + name)
    archive.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    cmd, active, manifest = inventory(root)
    with tempfile.TemporaryDirectory(dir=archive.parent) as tmp:
        stage = Path(tmp)
        run("docker", "image", "save", "-o", stage / "images.tar", *sorted(set(manifest["images"].values())))
        print("Stopping services for the filesystem snapshot…", flush=True)
        with stopped_for_snapshot(cmd, active, root / "redis_data" if manifest["volatile_redis"] else None):
            if not (root / "redis_data/dump.rdb").is_file():
                raise ValueError("Missing Redis snapshot in redis_data/dump.rdb")
            project_snapshot(root, stage / "project.tar")
        print("Services restarted. Compressing the archive…", flush=True)
        packed = stage / "backup.zip"
        with zipfile.ZipFile(packed, "x", zipfile.ZIP_DEFLATED, compresslevel=1) as bundle:
            bundle.writestr("manifest.json", json.dumps(manifest))
            bundle.write(__file__, "deployment_backup.py")
            launcher = Path(__file__).resolve().parent.parent / "backup.sh"
            if launcher.is_file():
                bundle.write(launcher, "backup.sh")
            runtime = os.environ.get("XRAY_BACKUP_RUNTIME")
            if runtime:
                bundle.write(runtime, "runtime/" + Path(runtime).name, compress_type=zipfile.ZIP_STORED)
            for name in ("project.tar", "images.tar"):
                bundle.write(stage / name, name)
        os.chmod(packed, 0o600)
        os.link(packed, archive)  # Publish only a finished archive, without overwriting.
    print("Backup saved to", archive)


def unpack_project(bundle, root):
    def portable_member(member, destination):
        # data_filter checks paths, link targets and file types. Keep the original
        # Unix metadata because Postgres and support uploads use different UIDs.
        if Path(member.name).is_absolute():
            raise ValueError("Absolute archive path: " + member.name)
        safe = tarfile.data_filter(member, destination)
        return safe.replace(uid=member.uid, gid=member.gid, mode=member.mode)

    with bundle.open("project.tar") as stream, tarfile.open(fileobj=stream, mode="r|", errorlevel=2) as tar:
        tar.extractall(root, numeric_owner=True, filter=portable_member)
        while stream.read(1024 * 1024):  # Consume tar padding and verify the ZIP CRC.
            pass


def restore(archive, root):
    if root.exists():
        raise ValueError("Restore requires a new directory: " + str(root))
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        if manifest["format"] != 1:
            raise ValueError("Unsupported backup format")
        if output("docker", "info", "-f", "{{.Architecture}}") != manifest["architecture"]:
            raise ValueError("Restore requires the same Docker host architecture")
        project = manifest["project"]
        if containers("label=" + LABEL + "project=" + project):
            raise ValueError("Compose project already exists on this Docker host: " + project)
        root.parent.mkdir(parents=True, exist_ok=True)
        root.mkdir(mode=0o700)
        try:
            unpack_project(bundle, root)
            for name in [*manifest["files"], ".env", "config.yml", "pg_data/PG_VERSION", "redis_data/dump.rdb"]:
                path = (root / name).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    raise ValueError("Missing or external restore file: " + name)
            with tempfile.TemporaryDirectory(dir=root.parent) as tmp:
                saved = Path(tmp) / "images.tar"
                with bundle.open("images.tar") as source, saved.open("xb") as target:
                    shutil.copyfileobj(source, target)
                run("docker", "image", "load", "-i", saved)
            services = {}
            for service, image in manifest["images"].items():
                tag = "xray-recovery:" + image.removeprefix("sha256:")
                run("docker", "image", "tag", image, tag)
                services[service] = {"image": tag}
            override = root / IMAGE_OVERRIDE
            if override.exists():
                if IMAGE_OVERRIDE not in manifest["files"] or override.is_symlink():
                    raise ValueError("Recovery filename already in use: " + IMAGE_OVERRIDE)
                override.unlink()
            with override.open("x") as file:
                json.dump({"services": services}, file, indent=2)
            files = [f for f in manifest["files"] if f != IMAGE_OVERRIDE] + [IMAGE_OVERRIDE]
            cmd = compose(root, project, files)
            config = json.loads(output(*cmd, "config", "--format", "json"))
            for service in services:
                for mount in config["services"][service].get("volumes", []):
                    path = Path(mount.get("source", "")).resolve()
                    if mount["type"] != "bind" or not path.is_relative_to(root) or not path.exists():
                        raise ValueError("Non-portable restored mount in " + service)
            existing = set(output("docker", "ps", "-a", "--format", "{{.Names}}").splitlines())
            for service in services:
                if config["services"][service].get("container_name") in existing:
                    raise ValueError("Container name already in use for " + service)
        except BaseException:
            shutil.rmtree(root)
            raise
    networks = set(output("docker", "network", "ls", "--format", "{{.Name}}").splitlines())
    for network in config["networks"].values():
        if network.get("external") and network["name"] not in networks:
            run("docker", "network", "create", network["name"])
    up = [*cmd, "up", "-d", "--pull", "never", "--no-build", "--wait", "--wait-timeout", "300"]
    start = [*up, *manifest["active"]]
    if manifest["volatile_redis"]:
        run(*up, "redis")
        finish_redis_boot(root / "redis_data")
    print("Starting restored project. To retry startup:", shlex.join(start), flush=True)
    run(*start)
    print("Restored services are ready in", root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    save = commands.add_parser("backup", help="snapshot the deployment, briefly stopping running services")
    save.add_argument("archive", type=Path, help="new ZIP path outside the project")
    save.add_argument("--project-dir", type=Path, default=Path.cwd())
    recover = commands.add_parser("restore", help="extract and start on a clean Docker host")
    recover.add_argument("archive", type=Path)
    recover.add_argument("directory", type=Path, help="new project directory")
    args = parser.parse_args()
    if not sys.platform.startswith("linux") or os.geteuid() != 0 or not hasattr(tarfile, "data_filter"):
        parser.error("Run as root on Linux with Python 3.12+ (or a Python with tarfile.data_filter)")
    os.umask(0o077)
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    import fcntl

    # The deployment uses fixed container names. Serialize checks and startup
    # even when two restores choose different destination directories.
    with open("/run/xray-deployment-backup.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "Another deployment backup or restore is in progress.\n")
        if args.action == "backup":
            backup(args.project_dir.resolve(), args.archive.resolve())
        else:
            restore(args.archive.resolve(), args.directory.resolve())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile) as exc:
        sys.exit(str(exc))
