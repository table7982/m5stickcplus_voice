#!/usr/bin/env python3
"""
Low-latency Codex -> M5StickC Plus bridge.

It tails the active Codex JSONL session and sends one-line serial commands:
  THINK  model/reasoning is active
  TYPE   Codex is editing/running tools
  SPEAK  Codex is writing visible text
  DONE   task completed; board returns to idle and beeps
  IDLE   quiet timeout
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


BAUD = 115200
POLL_SECONDS = 0.05
RESCAN_SESSION_SECONDS = 1.5
IDLE_AFTER_SECONDS = 18.0

STATE_PRIORITY = {
    "": 0,
    "IDLE": 0,
    "THINK": 1,
    "SPEAK": 2,
    "TYPE": 3,
    "DONE": 4,
}

TYPE_TOOL_NAMES = {
    "apply_patch",
    "exec_command",
    "write_stdin",
    "automation_update",
    "imagegen",
}

TYPE_PAYLOAD_TYPES = {
    "custom_tool_call",
    "function_call",
    "patch_apply_begin",
    "patch_apply_end",
}

THINK_PAYLOAD_TYPES = {
    "task_started",
    "turn_started",
    "reasoning",
    "agent_reasoning",
}

SPEAK_PAYLOAD_TYPES = {
    "agent_message",
    "message",
    "agent_message_delta",
    "response_output_text_delta",
}

DONE_PAYLOAD_TYPES = {
    "task_complete",
    "task_completed",
    "turn_complete",
    "turn_completed",
}


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def sessions_root() -> Path:
    return codex_home() / "sessions"


def latest_session_file() -> Optional[Path]:
    root = sessions_root()
    if not root.exists():
        return None
    newest: Optional[Path] = None
    newest_mtime = -1.0
    for path in root.rglob("*.jsonl"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > newest_mtime:
            newest = path
            newest_mtime = mtime
    return newest


def autodetect_port() -> Optional[str]:
    system = platform.system().lower()
    if system == "windows":
        try:
            output = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-PnpDevice -Class Ports | "
                    "Where-Object {$_.FriendlyName -match 'USB|Serial|CH910|CH340|CP210|FTDI'} | "
                    "ForEach-Object { if ($_.FriendlyName -match '\\((COM\\d+)\\)') { $Matches[1] } }",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            ports = [line.strip() for line in output.splitlines() if line.strip()]
            return ports[-1] if ports else None
        except Exception:
            return None

    patterns = [
        "/dev/cu.usbserial*",
        "/dev/cu.usbmodem*",
        "/dev/cu.wchusbserial*",
        "/dev/cu.SLAB_USBtoUART*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
    ]
    ports: list[str] = []
    for pattern in patterns:
        ports.extend(glob.glob(pattern))
    return sorted(ports)[0] if ports else None


class Sender:
    def __init__(self, port: str, baud: int = BAUD) -> None:
        self.port = port
        self.baud = baud
        self.serial = None
        try:
            import serial  # type: ignore

            self.serial = serial.Serial(port, baudrate=baud, timeout=0, write_timeout=0.2)
            time.sleep(1.0)
        except Exception:
            self.serial = None
            if platform.system().lower() != "windows":
                subprocess.run(["stty", "-f", port, str(baud), "cs8", "-cstopb", "-parenb"], check=False)

    def send(self, command: str) -> None:
        command = command.strip().upper()
        line = (command + "\n").encode("ascii")
        if self.serial is not None:
            self.serial.write(line)
            self.serial.flush()
            return

        if platform.system().lower() == "windows":
            ps = (
                "$p = New-Object System.IO.Ports.SerialPort "
                f"'{self.port}',{self.baud},'None',8,'one'; "
                "$p.Open(); "
                f"$p.WriteLine('{command}'); "
                "$p.Close()"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
        else:
            with open(self.port, "wb", buffering=0) as handle:
                handle.write(line)

    def close(self) -> None:
        if self.serial is not None:
            self.serial.close()


@dataclass
class TailState:
    path: Optional[Path] = None
    offset: int = 0
    last_scan: float = 0.0


def compact_raw(line: str) -> str:
    return re.sub(r"\s+", "", line.lower())


def parse_json_line(line: str) -> Optional[dict]:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def classify_record(record: dict, raw_line: str) -> str:
    payload = record.get("payload")
    event_type = str(record.get("type") or "")
    payload_type = ""
    role = ""
    name = ""
    phase = ""

    if isinstance(payload, dict):
        payload_type = str(payload.get("type") or "")
        role = str(payload.get("role") or "")
        name = str(payload.get("name") or "")
        phase = str(payload.get("phase") or "")

    if payload_type in DONE_PAYLOAD_TYPES or event_type in DONE_PAYLOAD_TYPES:
        return "DONE"

    if phase == "final_answer":
        return "SPEAK"

    if payload_type in TYPE_PAYLOAD_TYPES:
        if name in TYPE_TOOL_NAMES or payload_type in {"patch_apply_begin", "patch_apply_end"}:
            return "TYPE"
        return "TYPE"

    if payload_type in {"custom_tool_call_output", "function_call_output"}:
        return "TYPE" if looks_like_file_work(raw_line) else ""

    if name in TYPE_TOOL_NAMES:
        return "TYPE"

    if payload_type in SPEAK_PAYLOAD_TYPES:
        return "SPEAK"

    if role == "assistant":
        return "SPEAK"

    if payload_type in THINK_PAYLOAD_TYPES or event_type in THINK_PAYLOAD_TYPES:
        return "THINK"

    return ""


def looks_like_file_work(raw_line: str) -> bool:
    raw = raw_line.lower()
    return any(
        token in raw
        for token in (
            "success. updated the following files",
            "apply_patch",
            "patch_apply",
            "exec_command",
            "write_stdin",
            "created file",
            "deleted file",
            "modified",
            ".ino",
            ".py",
            ".js",
            ".ts",
            ".cpp",
            ".h",
            ".md",
        )
    )


def classify_raw(line: str) -> str:
    raw = line.lower()
    compact = compact_raw(line)

    if '"type":"task_complete"' in compact or '"type":"turn_complete"' in compact:
        return "DONE"

    if '"phase":"final_answer"' in compact:
        return "SPEAK"

    if '"type":"agent_message"' in compact:
        return "SPEAK"

    if '"role":"assistant"' in compact and '"type":"message"' in compact:
        return "SPEAK"

    if any(token in compact for token in ('"type":"custom_tool_call"', '"type":"function_call"', '"type":"patch_apply_end"', '"type":"patch_apply_begin"')):
        return "TYPE"

    if looks_like_file_work(raw):
        return "TYPE"

    if '"type":"reasoning"' in compact or '"type":"task_started"' in compact:
        return "THINK"

    return ""


def classify_line(line: str) -> str:
    record = parse_json_line(line)
    if record is not None:
        return classify_record(record, line) or classify_raw(line)
    return classify_raw(line)


def choose_state(states: list[str]) -> str:
    chosen = ""
    for state in states:
        if STATE_PRIORITY[state] >= STATE_PRIORITY[chosen]:
            chosen = state
    return chosen


def read_available(path: Path, offset: int) -> tuple[list[str], int]:
    try:
        size = path.stat().st_size
        if offset > size:
            offset = 0
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            lines = handle.readlines()
            return lines, handle.tell()
    except FileNotFoundError:
        return [], 0


def maybe_switch_session(tail: TailState, force: bool = False) -> bool:
    now = time.monotonic()
    if not force and now - tail.last_scan < RESCAN_SESSION_SECONDS:
        return False
    tail.last_scan = now
    latest = latest_session_file()
    if latest is None or latest == tail.path:
        return False
    tail.path = latest
    tail.offset = latest.stat().st_size
    return True


def run_bridge(port: str, session: Optional[str], debug: bool = False) -> None:
    sender = Sender(port)
    tail = TailState(path=Path(session).expanduser() if session else None)
    if tail.path and tail.path.exists():
        tail.offset = tail.path.stat().st_size
    else:
        maybe_switch_session(tail, force=True)

    last_sent = ""
    last_activity = time.monotonic()

    print(f"Serial port: {port}")
    print(f"Codex home: {codex_home()}")
    print("Watching Codex sessions. Press Ctrl+C to stop.")
    if tail.path:
        print(f"Watching session: {tail.path}")
    sender.send("IDLE")
    last_sent = "IDLE"

    try:
        while True:
            if session is None and maybe_switch_session(tail):
                print(f"Watching session: {tail.path}")

            states: list[str] = []
            if tail.path:
                lines, tail.offset = read_available(tail.path, tail.offset)
                for line in lines:
                    state = classify_line(line)
                    if state:
                        states.append(state)
                    if debug and state:
                        print(f"{state:5} {line[:140].replace(chr(9), ' ')}")

            state = choose_state(states)
            if state:
                if state != last_sent:
                    sender.send(state)
                    print(f"-> {state}")
                    last_sent = state
                last_activity = time.monotonic()
                if state == "DONE":
                    time.sleep(0.9)
                    sender.send("IDLE")
                    print("-> IDLE")
                    last_sent = "IDLE"

            if last_sent not in {"IDLE", "DONE"} and time.monotonic() - last_activity > IDLE_AFTER_SECONDS:
                sender.send("IDLE")
                print("-> IDLE")
                last_sent = "IDLE"

            time.sleep(POLL_SECONDS)
    finally:
        sender.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror Codex activity to M5StickC Plus serial states.")
    parser.add_argument("--port", help="Serial port, e.g. COM5 or /dev/cu.usbserial-0001")
    parser.add_argument("--session", help="Optional Codex JSONL session file to tail instead of auto-detecting latest.")
    parser.add_argument("--send", help="Send one command and exit: IDLE, THINK, TYPE, SPEAK, DONE, BEEP")
    parser.add_argument("--debug", action="store_true", help="Print detected log lines.")
    args = parser.parse_args()

    port = args.port or autodetect_port()
    if not port:
        print("No serial port found. Pass --port COM5 or --port /dev/cu.usbserial-xxxx.", file=sys.stderr)
        return 2

    if args.send:
        sender = Sender(port)
        try:
            sender.send(args.send)
            print(f"Sent {args.send.strip().upper()} to {port}")
        finally:
            sender.close()
        return 0

    run_bridge(port, session=args.session, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
