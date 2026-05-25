#!/usr/bin/env python3
"""Codex / Claude Code hook 入口：把 hook stdin 转成统一事件写入队列。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_event_detector import map_hook_to_event
from config import EVENT_QUEUE_PATH, HOOK_DEBUG_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Write AI hook event to local queue.")
    parser.add_argument("--source", choices=["codex", "claude"], required=True)
    args = parser.parse_args()

    raw_stdin = sys.stdin.read()
    payload = parse_payload(raw_stdin)
    hook_event_name = str(payload.get("hook_event_name") or payload.get("event") or "")
    event = map_hook_to_event(args.source, hook_event_name, payload, raw_stdin)
    write_debug(args.source, hook_event_name, event, raw_stdin)

    # 未映射事件先忽略，避免队列里塞太多无用日志。
    if not event:
        return 0

    record = {
        "time": time.time(),
        "source": args.source,
        "event": event,
        "hook_event_name": hook_event_name,
        "cwd": payload.get("cwd") or os.getcwd(),
        "session_id": payload.get("session_id") or payload.get("transcript_path"),
    }
    write_event(record)
    return 0


def parse_payload(raw_stdin: str) -> dict:
    """hook stdin 通常是 JSON；解析失败时保留原文。"""
    try:
        payload = json.loads(raw_stdin) if raw_stdin.strip() else {}
    except json.JSONDecodeError:
        return {"raw": raw_stdin}
    return payload if isinstance(payload, dict) else {"raw": payload}


def write_event(record: dict) -> None:
    """追加一行 JSON 到本地事件队列。"""
    EVENT_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with EVENT_QUEUE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_debug(source: str, hook_event_name: str, event: str, raw_stdin: str) -> None:
    """无论是否识别成功，都记录 hook 调试信息。"""
    HOOK_DEBUG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time": time.time(),
        "source": source,
        "hook_event_name": hook_event_name,
        "event": event,
        "stdin_preview": raw_stdin[:500],
    }
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with HOOK_DEBUG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
