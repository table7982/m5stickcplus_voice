"""AI 事件检测模块：读取 hook_emit.py 写入的事件队列。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from config import EVENT_QUEUE_PATH


# 统一事件名，主程序不直接依赖 Codex / Claude 的原始 hook 格式。
EVENT_WORKING = "WORKING"
EVENT_TOOL = "TOOL"
EVENT_SPEAKING = "SPEAKING"
EVENT_WAITING = "WAITING"
EVENT_DONE = "DONE"


def new_tail(queue_path: Optional[str] = None) -> dict:
    """创建 hook 事件队列的 tail 状态，默认从文件末尾开始读。"""
    path = Path(queue_path).expanduser() if queue_path else EVENT_QUEUE_PATH
    return {
        "path": path,
        "offset": path.stat().st_size if path.exists() else 0,
    }


def poll_events(tail: dict, source_filter: str = "both") -> list[dict]:
    """读取 hook 队列新增事件。"""
    lines, tail["offset"] = read_available(tail["path"], tail["offset"])
    records: list[dict] = []

    for line in lines:
        record = parse_event_line(line)
        if record is None:
            continue

        source = str(record.get("source") or "")
        event = str(record.get("event") or "")
        if not event:
            continue
        if source_filter != "both" and source != source_filter:
            continue

        records.append(record)

    return records


def read_available(path: Path, offset: int) -> tuple[list[str], int]:
    """从上次偏移量开始读取新增内容。"""
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


def parse_event_line(line: str) -> Optional[dict]:
    """队列每行都是一个 JSON 事件。"""
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def map_hook_to_event(source: str, hook_event_name: str, payload: dict, raw_stdin: str = "") -> str:
    """把 Codex / Claude Code hook 名称转换成统一事件。"""
    name = hook_event_name.strip()
    raw = raw_stdin.lower()

    if name == "UserPromptSubmit":
        return EVENT_WORKING
    if name == "PreToolUse":
        return EVENT_TOOL
    if name == "PostToolUse":
        return EVENT_WORKING
    if name == "PermissionRequest":
        return EVENT_WAITING
    if name == "Notification":
        return EVENT_WAITING if looks_like_waiting(payload, raw) else EVENT_SPEAKING
    if name in {"Stop", "StopFailure", "SubagentStop"}:
        return EVENT_DONE
    if name in {"SessionStart", "SubagentStart"}:
        return EVENT_WORKING

    # 部分工具可能不给 hook_event_name，保留关键词兜底。
    if "permission" in raw or "approval" in raw or "idle_prompt" in raw:
        return EVENT_WAITING
    if "pretooluse" in raw or "tool_use" in raw:
        return EVENT_TOOL
    if "stop" in raw or "end_turn" in raw:
        return EVENT_DONE
    return ""


def looks_like_waiting(payload: dict, raw: str) -> bool:
    """识别等待用户输入、权限确认或空闲提示。"""
    notification_type = str(payload.get("notification_type") or "").lower()
    if notification_type in {"permission_prompt", "idle_prompt", "elicitation_dialog"}:
        return True

    return any(
        token in raw
        for token in (
            "permission",
            "approval",
            "idle_prompt",
            "elicitation_dialog",
            "waiting_for_user",
            "request_user_input",
        )
    )
