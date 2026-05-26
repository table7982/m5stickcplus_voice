#!/usr/bin/env python3
"""程序入口：检测 AI 事件，并通过串口通知 M5StickC Plus。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# 允许直接运行：python3 codex_bridge_refactor/main.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_event_detector import new_tail, poll_events
from config import BAUD, POLL_SECONDS
from serial_sender import autodetect_port, close_sender, open_sender, send_command
from state_controller import handle_events, mark_sent, new_controller, tick


def run(args: argparse.Namespace) -> int:
    """主循环：事件检测 -> 状态控制 -> 串口发送。"""
    sender = None
    port = None
    if not args.debug:
        port = args.port or autodetect_port()
        if not port:
            print("No serial port found. Pass --port COM5 or --port /dev/cu.usbserial-xxxx.", file=sys.stderr)
            return 2
        try:
            sender = open_sender(port, BAUD)
        except Exception as exc:
            print(f"Failed to open serial port {port}: {exc}", file=sys.stderr)
            return 1

    try:
        if args.send:
            if args.debug:
                print(f"debug send: {args.send.strip().upper()}")
                return 0
            command = args.send.strip().upper()
            try:
                send_command(sender, command)
            except Exception as exc:
                print(f"Failed to send {command}: {exc}", file=sys.stderr)
                return 1
            print(f"Sent {command} to {port}")
            return 0

        tail = new_tail(args.queue)
        controller = new_controller()

        if args.debug:
            print("Debug mode: serial sending disabled.")
        else:
            print(f"Serial port: {port}")
        print(f"Source: {args.source}")
        print(f"Event queue: {tail['path']}")
        if args.debug:
            print("Waiting for hook events. Serial commands will be printed instead of sent.")
        print("Press Ctrl+C to stop.")

        if not args.debug:
            send_command(sender, "IDLE")
        mark_sent(controller, "IDLE")

        try:
            while True:
                records = poll_events(tail, source_filter=args.source)
                events = [str(record["event"]) for record in records]
                for record in records:
                    # 调试观察用：每次检测到事件都打印一条简洁日志。
                    hook_name = record.get("hook_event_name") or "unknown"
                    print(f"event source={record.get('source')} event={record.get('event')} hook={hook_name}")

                command = handle_events(controller, events) or tick(controller)
                if command:
                    if args.debug:
                        print(f"serial command={command} debug=true")
                    else:
                        send_command(sender, command)
                        print(f"serial command={command}")

                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("Stopped.")
    finally:
        if sender is not None:
            close_sender(sender)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror Codex / Claude Code activity to M5StickC Plus.")
    parser.add_argument("--port", help="Serial port, e.g. COM5 or /dev/cu.usbserial-0001")
    parser.add_argument("--source", choices=["codex", "claude", "both"], default="both", help="Which AI logs to watch.")
    parser.add_argument("--queue", help="Optional hook event queue path.")
    parser.add_argument("--send", help="Send one command and exit: IDLE, THINK, TYPE, SPEAK, DONE, BEEP")
    parser.add_argument("--debug", action="store_true", help="Watch events without opening or writing serial port.")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
