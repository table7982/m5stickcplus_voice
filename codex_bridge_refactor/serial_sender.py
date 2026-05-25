"""串口发送模块：只负责找串口、打开串口、发送开发板命令。"""

from __future__ import annotations

import glob
import platform
import subprocess
import time
from typing import Optional

from config import BAUD


def autodetect_port() -> Optional[str]:
    """自动寻找常见的 USB 串口。"""
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


def open_sender(port: str, baud: int = BAUD) -> dict:
    """打开串口；如果没有 pyserial，就使用系统命令兜底。"""
    sender = {"port": port, "baud": baud, "serial": None}
    try:
        import serial  # type: ignore

        sender["serial"] = serial.Serial(port, baudrate=baud, timeout=0, write_timeout=0.2)
        time.sleep(1.0)
    except Exception:
        if platform.system().lower() != "windows":
            subprocess.run(["stty", "-f", port, str(baud), "cs8", "-cstopb", "-parenb"], check=False)
    return sender


def send_command(sender: dict, command: str) -> None:
    """向开发板发送一行 ASCII 命令。"""
    command = command.strip().upper()
    line = (command + "\n").encode("ascii")
    serial_handle = sender.get("serial")

    if serial_handle is not None:
        serial_handle.write(line)
        serial_handle.flush()
        return

    port = sender["port"]
    baud = sender["baud"]
    if platform.system().lower() == "windows":
        ps = (
            "$p = New-Object System.IO.Ports.SerialPort "
            f"'{port}',{baud},'None',8,'one'; "
            "$p.Open(); "
            f"$p.WriteLine('{command}'); "
            "$p.Close()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    else:
        with open(port, "wb", buffering=0) as handle:
            handle.write(line)


def close_sender(sender: dict) -> None:
    """关闭 pyserial 打开的串口。"""
    serial_handle = sender.get("serial")
    if serial_handle is not None:
        serial_handle.close()

