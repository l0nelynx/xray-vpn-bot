"""Operator smoke test for Remnawave API v3.

Read-only by default. ``--mutating`` creates a uniquely marked disposable
profile, updates and resets it, reads HWID devices, and deletes it in ``finally``.
The script never prints the API token or subscription URL.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
from pathlib import Path
import uuid

import yaml

from remnawave_client import configure


def _config(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def _verify_distribution() -> None:
    version = importlib.metadata.version("remnawave-api")
    if version != "3.0.1":
        raise RuntimeError(f"unexpected remnawave-api version: {version}")
    try:
        legacy = importlib.metadata.version("remnawave")
    except importlib.metadata.PackageNotFoundError:
        return
    raise RuntimeError(f"conflicting legacy remnawave distribution installed: {legacy}")


async def _run(args: argparse.Namespace) -> dict:
    _verify_distribution()
    config = _config(args.config)
    base_url = str(config.get("remnawave_url") or "").strip()
    token = str(config.get("remnawave_token") or "").strip()
    if not base_url or not token:
        raise RuntimeError("remnawave_url/remnawave_token are missing")

    client = configure(
        base_url=base_url,
        token=token,
        free_squad_id=str(config.get("rw_free_id") or "") or None,
    )
    report: dict[str, object] = {
        "sdk_distribution": "remnawave-api==3.0.1",
        "mode": "mutating" if args.mutating else "read-only",
    }

    if args.rw_id is not None:
        user = await client.get_user_by_id(args.rw_id, raise_on_error=True)
        if user is None:
            raise RuntimeError(f"rw_id {args.rw_id} was not found")
        devices = await client.get_user_hwid_devices_by_id(args.rw_id)
        if devices is None:
            raise RuntimeError(f"HWID lookup failed for rw_id {args.rw_id}")
        report["read"] = {
            "rw_id": user.get("rw_id"),
            "username": user.get("username"),
            "status": user.get("status"),
            "hwid_devices": int(devices.total or len(devices.devices or [])),
        }

    if not args.mutating:
        return report

    nonce = uuid.uuid4().hex
    username = f"smoke_{nonce[:12]}"
    marker = f"stage2-smoke:{nonce}"
    created_rw_id: int | None = None
    cleanup_ok = False
    try:
        created = await client.create_user(
            username=username,
            telegram_id=0,
            days=1,
            descr=marker,
            tag="STAGE2_SMOKE",
            raise_on_error=True,
        )
        if not created or created.get("rw_id") is None:
            raise RuntimeError("create returned no rw_id")
        created_rw_id = int(created["rw_id"])

        updated = await client.update_user_by_id(
            created_rw_id,
            descr=f"{marker}; updated",
            status="active",
            raise_on_error=True,
        )
        if not updated or int(updated.get("rw_id") or 0) != created_rw_id:
            raise RuntimeError("update did not return the created rw_id")
        if not await client.reset_user_traffic_by_id(created_rw_id):
            raise RuntimeError("traffic reset failed")
        devices = await client.get_user_hwid_devices_by_id(created_rw_id)
        if devices is None:
            raise RuntimeError("HWID list failed")
        report["mutation"] = {
            "created_rw_id": created_rw_id,
            "updated": True,
            "traffic_reset": True,
            "hwid_list": True,
        }
    finally:
        if created_rw_id is not None:
            cleanup_ok = await client.delete_user_by_id(created_rw_id)
            report["cleanup_deleted"] = cleanup_ok

    if created_rw_id is not None and not cleanup_ok:
        raise RuntimeError(
            f"smoke profile cleanup failed; delete rw_id {created_rw_id} manually"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--rw-id", type=int, help="existing profile for read/HWID test")
    parser.add_argument(
        "--mutating",
        action="store_true",
        help="create, update, reset and delete a disposable smoke profile",
    )
    args = parser.parse_args()
    try:
        report = asyncio.run(_run(args))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
