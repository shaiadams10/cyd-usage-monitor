#!/usr/bin/env python3
"""Recover existing monitor containers after a delayed LAN/Docker startup."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


SERVICES = ("cyd-monitor-app", "cyd-monitor-collector", "cloudflared")
UNIT = "cyd-monitor-recovery"


def run(args, timeout=20):
    # Docker errors can contain private bind addresses. Never echo captured output.
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=True).stdout


def needs_recovery(info, now=None):
    state = info["state"]
    status = state.get("Status")
    if status in {"created", "exited", "dead"}:
        return True
    if status != "running":
        return False  # Preserve paused containers and Docker's active restart loop.
    mode = info.get("mode", "")
    if mode not in {"", "default", "bridge", "host", "none"} and not mode.startswith("container:"):
        if mode not in (info.get("networks") or {}):
            return True  # Failed port binding can leave a running, disconnected app.
    if state.get("Health", {}).get("Status") != "unhealthy":
        return False
    # Bound restarts of an unhealthy service to once per five minutes.
    started = dt.datetime.fromisoformat(state["StartedAt"].replace("Z", "+00:00"))
    return ((now or dt.datetime.now(dt.timezone.utc)) - started).total_seconds() >= 300


def recover(project_dir):
    compose = ["docker", "compose", "--project-directory", str(project_dir)]
    failed = False
    for service in SERVICES:
        try:
            ids = run(compose + ["ps", "--all", "--quiet", service]).split()
            if len(ids) != 1:
                print(f"{service}: expected one existing container; deploy with Compose first", flush=True)
                failed = True
                continue
            template = '{"state":{{json .State}},"mode":{{json .HostConfig.NetworkMode}},"networks":{{json .NetworkSettings.Networks}}}'
            info = json.loads(run(["docker", "inspect", "--format", template, ids[0]]))
            if needs_recovery(info):
                print(f"{service}: recovering service and network attachment", flush=True)
                run(compose + ["up", "-d", "--no-deps", "--no-build", "--pull", "never",
                               "--force-recreate", service], timeout=40)
        except (subprocess.SubprocessError, OSError, ValueError, KeyError):
            print(f"{service}: recovery check failed; next timer run will retry", flush=True)
            failed = True
    return 1 if failed else 0


def unit_arg(value):
    value = str(value)
    if any(char in value for char in "\r\n\x00"):
        raise ValueError("Invalid unit argument")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'


def install(project_dir):
    if sys.platform != "linux":
        raise ValueError("Install on the Linux deployment host")
    if "Linger=yes" not in run(["loginctl", "show-user", str(os.getuid()), "-p", "Linger"]):
        raise ValueError("Enable lingering for the deployment user with loginctl enable-linger before installing")
    if not shutil.which("docker"):
        raise ValueError("Docker CLI is required")
    run(["docker", "compose", "--project-directory", str(project_dir), "config", "--quiet"])
    destination = Path.home() / ".local/lib/cyd-usage-monitor/recover-monitor.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if Path(__file__).resolve() != destination.resolve():
        temporary = destination.with_suffix(".tmp")
        shutil.copyfile(__file__, temporary)
        temporary.chmod(0o700)
        temporary.replace(destination)
    units = Path.home() / ".config/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    command = " ".join(map(unit_arg, [sys.executable, destination, "--project-dir", project_dir]))
    (units / f"{UNIT}.service").write_text(
        "[Unit]\nDescription=Recover CYD monitor services after network startup\n\n"
        f"[Service]\nType=oneshot\nExecStart={command}\nTimeoutStartSec=300\nUMask=0077\n",
        encoding="utf-8")
    (units / f"{UNIT}.timer").write_text(
        "[Unit]\nDescription=Retry CYD monitor recovery at boot and every minute\n\n"
        "[Timer]\nOnActiveSec=15s\nOnUnitInactiveSec=60s\nAccuracySec=5s\n\n"
        "[Install]\nWantedBy=timers.target\n", encoding="utf-8")
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "enable", "--now", f"{UNIT}.timer"])
    print("Recovery timer installed; deployment user lingering is enabled.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--install", action="store_true", help="Install boot + minute recovery for the current Linux user")
    args = parser.parse_args()
    project = args.project_dir.resolve()
    if not (project / "docker-compose.yml").is_file():
        parser.error("project directory must contain docker-compose.yml")
    if args.install:
        try:
            install(project)
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            # Only our own validation errors are safe to show.
            print(str(exc) if isinstance(exc, ValueError) else "Recovery installation failed; check Docker and user systemd access.", file=sys.stderr)
            return 1
        return 0
    return recover(project)


if __name__ == "__main__":
    sys.exit(main())
