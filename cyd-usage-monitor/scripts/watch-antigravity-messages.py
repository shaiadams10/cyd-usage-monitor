"""Event-driven Windows fallback for Antigravity builds not invoking hooks.

Waits in ReadDirectoryChangesW; no screen access or directory polling.
One minute health checks detect dead receiver threads and refresh status.
Only transcript.jsonl changes enter the bounded worker queue. Existing messages
at startup are ignored. Shares selection/deduplication with the Codex helper.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import struct
import subprocess
import sys
import threading
import time

spec = importlib.util.spec_from_file_location("chat_switch", Path(__file__).with_name("chat-account-switch.py"))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def notifications(data):
    offset = 0
    while offset + 12 <= len(data):
        next_offset, action, size = struct.unpack_from("<III", data, offset)
        if size % 2 or offset + 12 + size > len(data):
            return
        name = data[offset + 12:offset + 12 + size].decode("utf-16-le")
        if action in (1, 3, 5) and name.replace("\\", "/").endswith("/transcript.jsonl"):
            yield name
        if not next_offset or next_offset < 12:
            return
        offset += next_offset


def kernel():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE
    k.ReadDirectoryChangesW.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
        wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID, wintypes.LPVOID]
    k.ReadDirectoryChangesW.restype = wintypes.BOOL
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k.CreateMutexW.restype = wintypes.HANDLE
    return k


def watch(config_path):
    k = kernel()
    name = hashlib.sha256(str(config_path.resolve()).casefold().encode()).hexdigest()[:20]
    mutex = k.CreateMutexW(None, False, "Local\\CYDAntigravityMessages-" + name)
    if not mutex:
        raise OSError("Mutex unavailable")
    if ctypes.get_last_error() == 183:
        k.CloseHandle(mutex)
        return
    started = time.time()
    config = json.loads(config_path.read_text(encoding="utf8"))
    status_path = config_path.parent / "antigravity-watcher-status.json"
    changes = queue.Queue(maxsize=256)
    handles = []
    receivers = []
    last_status = [0.0]

    def status(value):
        now = time.time()
        temporary = status_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"time": now, "started_at": started, "status": value,
                                        "pid": os.getpid(), "roots": len(handles)}), encoding="utf8")
        os.replace(temporary, status_path)
        last_status[0] = now

    def receive(root, handle):
        buffer = ctypes.create_string_buffer(64 * 1024)
        count = wintypes.DWORD()
        while True:
            ok = k.ReadDirectoryChangesW(handle, buffer, len(buffer), True,
                0x01 | 0x10, ctypes.byref(count), None, None)
            if not ok:
                helper.diagnostic(config_path.parent / "chat-switch.sqlite", "watcher", "watch_failed", stage="watch")
                return
            if count.value == 0:
                helper.diagnostic(config_path.parent / "chat-switch.sqlite", "watcher", "overflow", stage="watch")
                continue
            for name in notifications(buffer.raw[:count.value]):
                try:
                    changes.put_nowait(root / name)
                except queue.Full:
                    helper.diagnostic(config_path.parent / "chat-switch.sqlite", "watcher", "overflow", stage="watch")

    try:
        for raw in config["antigravity_roots"]:
            root = Path(raw).resolve()
            if not root.is_dir():
                continue
            handle = k.CreateFileW(str(root), 0x01, 0x01 | 0x02 | 0x04,
                                   None, 3, 0x02000000, None)
            if handle == ctypes.c_void_p(-1).value:
                raise OSError("Directory watch unavailable")
            handles.append(handle)
            receiver = threading.Thread(target=receive, args=(root, handle), daemon=True)
            receivers.append(receiver)
            receiver.start()
        if not handles:
            raise ValueError("No Antigravity brain directories")
        status("ready")
        helper.diagnostic(config_path.parent / "chat-switch.sqlite", "watcher", "ready", stage="startup")
        while True:
            if not all(receiver.is_alive() for receiver in receivers):
                raise OSError("Directory receiver stopped")
            if time.time() - last_status[0] >= 60:
                status("ready")
            try:
                path = changes.get(timeout=60)
            except queue.Empty:
                continue
            try:
                config = json.loads(config_path.read_text(encoding="utf8"))
                if not config.get("enabled"):
                    continue
                config["installed_at"] = max(started, config["installed_at"])
                # Expected layout: brain/<conversation>/.system_generated/logs/transcript.jsonl
                if path.parent.name != "logs" or path.parent.parent.name != ".system_generated":
                    continue
                event = {"conversationId": path.parent.parent.parent.name,
                         "transcriptPath": str(path)}
                result = helper.run("antigravity", event, config,
                                    config_path.parent / "chat-switch.sqlite", source="antigravity-watch")
                if result in ("ignored", "duplicate"):
                    continue
            except Exception as error:
                result = "unavailable"
                helper.diagnostic(config_path.parent / "chat-switch.sqlite", "watcher", result,
                                  stage="watch", error=helper.error_code(error))
            # Do not let routine assistant transcript changes hide a selection result.
            (config_path.parent / "chat-switch-antigravity-last-result.json").write_text(
                json.dumps({"time": time.time(), "provider": "antigravity", "result": result}),
                encoding="utf8")
    finally:
        try:
            status("watch_failed")
        except OSError:
            pass
        for handle in handles:
            k.CloseHandle(handle)
        k.CloseHandle(mutex)


def install():
    target = helper.private_dir()
    destination = target / Path(__file__).name
    if Path(__file__).resolve() != destination.resolve():
        shutil.copy2(__file__, destination)
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        raise ValueError("pythonw.exe required for windowless startup")
    startup = Path(__file__).with_name("install-antigravity-startup.ps1")
    if startup.resolve() != (target / startup.name).resolve():
        shutil.copy2(startup, target / startup.name)
    # Disable only our ineffective legacy hook, preserving other customizations.
    hooks_path = Path.home() / ".gemini" / "config" / "hooks.json"
    if hooks_path.exists():
        hooks = json.loads(hooks_path.read_text(encoding="utf8"))
        if "cyd-account-switch" in hooks:
            shutil.copy2(hooks_path, hooks_path.with_name("hooks.json.cyd-backup-" + str(time.time_ns())))
            hooks["cyd-account-switch"]["enabled"] = False
            hooks_path.write_text(json.dumps(hooks, indent=2) + "\n", encoding="utf8")
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(target / startup.name), "-Pythonw", str(pythonw),
                    "-Watcher", str(destination)], check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    print("Antigravity file-event helper installed and started; Codex hooks unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--config", type=Path, default=helper.private_dir() / "chat-switch.json")
    args = parser.parse_args()
    if args.install:
        install()
    else:
        try:
            watch(args.config)
        except Exception as error:
            helper.diagnostic(args.config.parent / "chat-switch.sqlite", "watcher", "unavailable",
                              stage="startup", error=helper.error_code(error))
            raise SystemExit(1)
