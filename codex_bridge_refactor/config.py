"""桥接程序的基础配置。"""

import os
from pathlib import Path

BAUD = 115200
POLL_SECONDS = 0.05
IDLE_AFTER_SECONDS = 18.0
DONE_IDLE_DELAY_SECONDS = 0.9
MIN_COMMAND_INTERVAL_SECONDS = 0.15

# hook 脚本和主程序共用这个事件队列文件，默认放在项目内便于调试。
RUNTIME_DIR = Path(__file__).resolve().parent / "runtime"
EVENT_QUEUE_PATH = Path(
    os.environ.get("M5_AI_EVENT_QUEUE")
    or RUNTIME_DIR / "m5_ai_events.jsonl"
)

# hook 调试日志：确认 hook 是否执行、收到什么事件。
HOOK_DEBUG_PATH = Path(
    os.environ.get("M5_HOOK_DEBUG")
    or RUNTIME_DIR / "m5_hook_debug.log"
)
