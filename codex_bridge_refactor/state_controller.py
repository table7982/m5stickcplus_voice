"""状态控制模块：把统一事件转换成开发板命令，并处理去重和回到空闲。"""

from __future__ import annotations

import time
from typing import Optional

from ai_event_detector import EVENT_DONE, EVENT_SPEAKING, EVENT_TOOL, EVENT_WAITING, EVENT_WORKING
from config import DONE_IDLE_DELAY_SECONDS, IDLE_AFTER_SECONDS, MIN_COMMAND_INTERVAL_SECONDS


EVENT_PRIORITY = {
    EVENT_WORKING: 1,
    EVENT_SPEAKING: 2,
    EVENT_TOOL: 3,
    EVENT_WAITING: 4,
    EVENT_DONE: 5,
}

COMMAND_BY_EVENT = {
    EVENT_WORKING: "THINK",
    EVENT_SPEAKING: "SPEAK",
    EVENT_TOOL: "TYPE",
    # 当前开发板没有 WAITING 命令，先用 DONE 提示用户并回到空闲。
    EVENT_WAITING: "DONE",
    EVENT_DONE: "DONE",
}


def new_controller() -> dict:
    """创建状态控制器，用普通 dict 避免过度抽象。"""
    now = time.monotonic()
    return {
        "last_sent": "",
        "last_change": 0.0,
        "last_activity": now,
        "idle_due_at": None,
        "pending": None,
    }


def choose_event(events: list[str]) -> str:
    """同一轮多个事件时，选择优先级最高的事件。"""
    chosen = ""
    for event in events:
        if EVENT_PRIORITY.get(event, 0) >= EVENT_PRIORITY.get(chosen, 0):
            chosen = event
    return chosen


def handle_events(controller: dict, events: list[str]) -> Optional[str]:
    """处理新事件，必要时返回需要发送的开发板命令。"""
    event = choose_event(events)
    if not event:
        return None

    now = time.monotonic()
    controller["last_activity"] = now
    command = COMMAND_BY_EVENT.get(event)
    if command is None:
        return None

    if command == "DONE":
        controller["idle_due_at"] = now + DONE_IDLE_DELAY_SECONDS
    return request_command(controller, command, now, urgent=command == "DONE")


def tick(controller: dict) -> Optional[str]:
    """没有新事件时推进延迟命令和超时回 IDLE。"""
    now = time.monotonic()

    if controller["pending"] and now - controller["last_change"] >= MIN_COMMAND_INTERVAL_SECONDS:
        command = controller["pending"]
        controller["pending"] = None
        return mark_sent(controller, command, now)

    idle_due_at = controller["idle_due_at"]
    if idle_due_at is not None and now >= idle_due_at:
        controller["idle_due_at"] = None
        return request_command(controller, "IDLE", now, urgent=True)

    if controller["last_sent"] != "IDLE" and now - controller["last_activity"] > IDLE_AFTER_SECONDS:
        return request_command(controller, "IDLE", now, urgent=True)

    return None


def request_command(controller: dict, command: str, now: float, urgent: bool = False) -> Optional[str]:
    """去重和简单去抖，避免串口短时间刷屏。"""
    command = command.strip().upper()
    if command == controller["last_sent"]:
        return None

    if urgent or now - controller["last_change"] >= MIN_COMMAND_INTERVAL_SECONDS:
        controller["pending"] = None
        return mark_sent(controller, command, now)

    controller["pending"] = command
    return None


def mark_sent(controller: dict, command: str, now: Optional[float] = None) -> str:
    """记录已经发送的命令。"""
    controller["last_sent"] = command
    controller["last_change"] = time.monotonic() if now is None else now
    return command

