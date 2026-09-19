"""Install local user hooks without replacing existing customizations.

Run with the desktop app's Python on Windows. No provider secrets are accessed.
Only private account hashes and CYD profile mappings are saved outside Git.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

SOURCE = Path(__file__).with_name("chat-account-switch.py")
spec = importlib.util.spec_from_file_location("chat_switch", SOURCE)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".cyd-backup-" + str(time.time_ns())))
    temporary = path.with_name(path.name + ".cyd-tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def install():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--codex-executable", type=Path)
    parser.add_argument("--probe-antigravity-hooks", action="store_true",
                        help="Add a metadata-only native-hook discovery probe alongside the watcher")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise ValueError("Windows is required")
    target = helper.private_dir()
    target.mkdir(parents=True, exist_ok=True)
    legacy = Path(os.environ["LOCALAPPDATA"]) / "CYDUsageMonitor"
    if not (target / "chat-switch.json").exists() and (legacy / "chat-switch.json").exists():
        save(target / "chat-switch.json", load(legacy / "chat-switch.json", {}))
    exe = args.codex_executable
    if exe is None:
        candidates = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
        exe = max(candidates, key=lambda p: p.stat().st_mtime)
    if not exe.is_file() or not args.codex_home.is_dir():
        raise ValueError("Desktop Codex installation was not found")
    old = load(target / "chat-switch.json", {})
    config = dict(old, enabled=True, codex_home=str(args.codex_home.resolve()),
                  codex_executable=str(exe.resolve()), installed_at=time.time(),
                  antigravity_roots=[str(Path.home() / ".gemini" / p / "brain")
                                     for p in ("antigravity", "antigravity-ide")])
    accounts = helper.api_request("/api/v1/accounts")["accounts"]
    mappings = dict(old.get("codex_accounts", {}))
    for entry in accounts:
        if not entry.get("enabled") or entry.get("provider") != "codex":
            continue
        emails = re.findall(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}", entry.get("label", ""))
        if len(emails) == 1:
            key = helper.identity_key(emails[0])
            values = mappings.setdefault(key, [])
            if entry["id"] not in values:
                values.append(entry["id"])
    config["codex_accounts"] = mappings
    ag = [a["id"] for a in accounts if a.get("enabled") and a.get("provider") == "antigravity"]
    if config.get("antigravity_profile") not in ag:
        if len(ag) != 1:
            raise ValueError("Set antigravity_profile in the private configuration to choose an account")
        config["antigravity_profile"] = ag[0]
    # Verify identity read before changing any hooks. Never guess an unknown account.
    current = helper.codex_account(config)
    mapped = helper.profile_for_account(config, current) is not None
    installed = target / SOURCE.name
    if installed.exists():
        shutil.copy2(installed, installed.with_name(installed.name + ".backup-" + str(time.time_ns())))
    shutil.copy2(SOURCE, installed)
    save(target / "chat-switch.json", config)
    commands = {p: subprocess.list2cmdline([sys.executable, str(installed), p])
                for p in ("codex", "antigravity")}
    # Antigravity tokenizes hook commands with shell-style escaping even on
    # Windows. Forward slashes preserve paths through that parser.
    commands["antigravity"] = '"' + Path(sys.executable).as_posix() + '" "' + installed.as_posix() + '" antigravity'
    codex_path = args.codex_home / "hooks.json"
    hooks = load(codex_path, {"hooks": {}})
    groups = hooks.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
    # Remove only previous copies of our handler; preserve all other handlers/groups.
    for group in groups:
        group["hooks"] = [h for h in group.get("hooks", [])
                          if not any(str(p) in h.get("command", "") for p in
                                     (installed, legacy / SOURCE.name))]
    groups[:] = [g for g in groups if g.get("hooks")]
    groups.append({"hooks": [{"type": "command", "command": commands["codex"],
                              "timeout": 4, "async": False,
                              "statusMessage": "Selecting CYD account"}]})
    save(codex_path, hooks)
    ag_path = Path.home() / ".gemini" / "config" / "hooks.json"
    hooks = load(ag_path, {})
    hooks["cyd-account-switch"] = {"enabled": True, "PreInvocation": [
        {"type": "command", "command": commands["antigravity"], "timeout": 2}]}
    if args.probe_antigravity_hooks:
        hooks["cyd-native-hook-probe"] = {"enabled": True, "PreInvocation": [
            {"type": "command", "command": commands["antigravity"] + "-probe", "timeout": 2}]}
    save(ag_path, hooks)
    # Use Windows notifications because some desktop builds do not invoke the
    # documented global hook. This disables only our Antigravity hook.
    subprocess.run([sys.executable, str(SOURCE.with_name("watch-antigravity-messages.py")),
                    "--install"], check=True)
    print("Installed local message hooks; existing configurations backed up.")
    print("Mapped Codex identities:", len(mappings))
    print("Current Codex identity mapped:", mapped)
    print("Antigravity primary account configured: True")
    print("Review/trust the new Codex hook in the app's Hooks settings or /hooks.")
    print("Antigravity uses the windowless file-event helper; no app restart needed.")


if __name__ == "__main__":
    try:
        install()
    except Exception as error:
        # Exceptions may contain private paths, URLs, or response bodies.
        print("Installation could not finish (" + type(error).__name__ + "). Check private configuration.", file=sys.stderr)
        raise SystemExit(1)
