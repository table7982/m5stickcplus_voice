#!/usr/bin/env python3
"""程序入口：检测 AI 事件，并通过串口通知 M5StickC Plus。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Callable

# 允许直接运行：python3 codex_bridge_refactor/main.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_event_detector import new_tail, poll_events
from bluetooth_sender import (
    DEFAULT_BLUETOOTH_NAME,
    autodetect_bluetooth_port,
    close_bluetooth_sender,
    open_bluetooth_sender,
    send_bluetooth_command,
)
from config import BAUD, POLL_SECONDS
from serial_sender import autodetect_port, close_sender, open_sender, send_command
from state_controller import handle_events, mark_sent, new_controller, tick


def run(args: argparse.Namespace) -> int:
    """主循环：事件检测 -> 状态控制 -> 串口发送。"""
    sender = None
    port = None
    send_fn: Callable[[dict, str], None] = send_command
    close_fn: Callable[[dict], None] = close_sender
    transport_label = "serial"
    if not args.debug:
        if args.transport == "bluetooth":
            transport_label = "bluetooth"
            port = args.port or autodetect_bluetooth_port(args.bluetooth_name)
            open_fn = open_bluetooth_sender
            send_fn = send_bluetooth_command
            close_fn = close_bluetooth_sender
        else:
            port = args.port or autodetect_port()
            open_fn = open_sender

        if not port:
            if args.transport == "bluetooth":
                print(
                    "No bluetooth SPP port found. Pair the device first or pass --port COMx / --port /dev/cu.xxxx.",
                    file=sys.stderr,
                )
            else:
                print("No serial port found. Pass --port COM5 or --port /dev/cu.usbserial-xxxx.", file=sys.stderr)
            return 2
        try:
            sender = open_fn(port, BAUD)
        except Exception as exc:
            print(f"Failed to open {transport_label} port {port}: {exc}", file=sys.stderr)
            return 1

    try:
        if args.send:
            if args.debug:
                print(f"debug send: {args.send.strip().upper()}")
                return 0
            command = args.send.strip().upper()
            try:
                send_fn(sender, command)
            except Exception as exc:
                print(f"Failed to send {command}: {exc}", file=sys.stderr)
                return 1
            print(f"Sent {command} to {transport_label} port {port}")
            return 0

        tail = new_tail(args.queue)
        controller = new_controller()

        if args.debug:
            print("Debug mode: command sending disabled.")
        else:
            print(f"Transport: {transport_label}")
            print(f"Port: {port}")
        print(f"Source: {args.source}")
        print(f"Event queue: {tail['path']}")
        if args.debug:
            print("Waiting for hook events. Commands will be printed instead of sent.")
        print("Press Ctrl+C to stop.")

        if not args.debug:
            send_fn(sender, "IDLE")
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
                        send_fn(sender, command)
                        print(f"{transport_label} command={command}")

                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("Stopped.")
    finally:
        if sender is not None:
            close_fn(sender)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror Codex / Claude Code activity to M5StickC Plus.")
    parser.add_argument("--port", help="Serial port, e.g. COM5 or /dev/cu.usbserial-0001")
    parser.add_argument("--transport", choices=["serial", "bluetooth"], default="serial", help="Send commands over USB serial or Bluetooth SPP.")
    parser.add_argument("--bluetooth-name", default=DEFAULT_BLUETOOTH_NAME, help="Bluetooth device name used for SPP port autodetection.")
    parser.add_argument("--source", choices=["codex", "claude", "both"], default="both", help="Which AI logs to watch.")
    parser.add_argument("--queue", help="Optional hook event queue path.")
    parser.add_argument("--send", help="Send one command and exit: IDLE, THINK, TYPE, SPEAK, DONE, BEEP")
    parser.add_argument("--debug", action="store_true", help="Watch events without opening or writing serial port.")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
