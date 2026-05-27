"""蓝牙 SPP 发送模块：通过 pyserial 写入系统暴露的蓝牙虚拟串口。"""

from __future__ import annotations

import glob
import platform
import subprocess
from typing import Optional

from config import BAUD
from serial_sender import close_sender, open_sender, send_command


DEFAULT_BLUETOOTH_NAME = "M5StickCPlus-Bot"


def autodetect_bluetooth_port(device_name: str = DEFAULT_BLUETOOTH_NAME) -> Optional[str]:
    """自动寻找常见的蓝牙 SPP 虚拟串口。"""
    system = platform.system().lower()
    if system == "windows":
        try:
            output = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_SerialPort | "
                    f"Where-Object {{$_.Name -match 'Bluetooth|{device_name}|M5StickCPlus'}} | "
                    "ForEach-Object { $_.DeviceID }",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            ports = [line.strip() for line in output.splitlines() if line.strip()]
            return ports[-1] if ports else None
        except Exception:
            return None

    patterns = [
        f"/dev/cu.{device_name}*",
        f"/dev/cu.*{device_name}*",
        "/dev/cu.*M5StickCPlus*",
        "/dev/cu.*Bluetooth*",
        "/dev/rfcomm*",
    ]
    ports: list[str] = []
    for pattern in patterns:
        ports.extend(glob.glob(pattern))

    ports = [port for port in ports if "Incoming-Port" not in port]
    return sorted(set(ports))[0] if ports else None


def open_bluetooth_sender(port: str, baud: int = BAUD) -> dict:
    """使用 pyserial 打开蓝牙 SPP 虚拟串口。"""
    sender = open_sender(port, baud)
    sender["transport"] = "bluetooth"
    return sender


def send_bluetooth_command(sender: dict, command: str) -> None:
    """向蓝牙 SPP 虚拟串口发送一行 ASCII 命令。"""
    send_command(sender, command)


def close_bluetooth_sender(sender: dict) -> None:
    """关闭 pyserial 打开的蓝牙 SPP 虚拟串口。"""
    close_sender(sender)
