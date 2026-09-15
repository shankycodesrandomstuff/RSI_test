"""Linux namespace launcher for candidate source execution.

The candidate sees a temporary chroot containing only read-only Python runtime,
read-only worker/candidate files, empty proc, and a tmpfs. It has a new network
namespace and no host home, experiment logs, evaluator, or credentials.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TRUSTED = (ROOT / "trusted").resolve()
TIMEOUT_SECONDS = 12


class SandboxError(RuntimeError):
    pass


def _safe_under(root: Path, path: Path) -> Path:
    resolved_root, resolved_path = root.resolve(), path.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise SandboxError("sandbox path escaped the designated experiment directory")
    return resolved_path


def _shell_script() -> str:
    # $1 root directory (already within run dir); $2 trusted; $3 candidate; $4 tasks JSON.
    return r'''set -eu
root="$1"
trusted="$2"
candidate="$3"
tasks="$4"
ulimit -t 10
ulimit -v 262144
ulimit -u 32
mount --make-rprivate /
mount -t tmpfs -o size=96m,nosuid,nodev,noexec tmpfs "$root"
mkdir -p "$root/usr" "$root/trusted" "$root/candidate" "$root/tmp" "$root/proc"
mount --rbind /usr "$root/usr"
mount -o remount,ro,bind "$root/usr"
ln -s usr/bin "$root/bin"
ln -s usr/lib "$root/lib"
ln -s usr/lib64 "$root/lib64"
mount --bind "$trusted" "$root/trusted"
mount -o remount,ro,bind "$root/trusted"
: > "$root/candidate/optimizer.py"
mount --bind "$candidate" "$root/candidate/optimizer.py"
mount -o remount,ro,bind "$root/candidate/optimizer.py"
mount -t tmpfs -o size=16m,nosuid,nodev,noexec tmpfs "$root/tmp"
mount -t proc -o nosuid,nodev,noexec proc "$root/proc"
exec chroot "$root" /usr/bin/python3 -I /trusted/worker.py /candidate/optimizer.py "$tasks"
'''


def run_candidate(source_path: Path, task_list: list[tuple[str, int]], scratch_root: Path) -> dict[str, Any]:
    """Execute candidate once in containment and return only its trace JSON."""
    source_path = _safe_under(scratch_root.parent, source_path)
    scratch_root = _safe_under(scratch_root.parent, scratch_root)
    if not shutil.which("unshare"):
        raise SandboxError("unshare is unavailable; refusing to execute candidate source unsandboxed")
    rootfs = scratch_root / f"rootfs-{source_path.stem}"
    rootfs.mkdir(exist_ok=False)
    tasks_json = json.dumps([[name, seed] for name, seed in task_list], separators=(",", ":"))
    command = [
        "unshare", "--user", "--map-root-user", "--mount", "--net", "--pid", "--fork", "--kill-child", "--mount-proc",
        "/bin/sh", "-ceu", _shell_script(), "sandbox", str(rootfs), str(TRUSTED), str(source_path), tasks_json,
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}, timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxError(f"candidate timed out after {TIMEOUT_SECONDS}s") from exc
    finally:
        # The rootfs contents only existed as a private tmpfs mount. The host directory is inside the run dir.
        if rootfs.exists():
            rootfs.rmdir()
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        raise SandboxError(f"sandbox worker exit {completed.returncode}: {completed.stderr[-400:]}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SandboxError("sandbox returned invalid JSON") from exc
    if not isinstance(result, dict) or "error" in result:
        raise SandboxError(f"sandbox rejected candidate: {result.get('error', 'malformed output')}")
    result["sandbox_elapsed_seconds"] = elapsed
    return result
