# Python 串口桥接重构版

这个目录是重构后的独立版本，不修改原来的 `codex_bridge/codex_m5_bridge.py`。当前版本不再读取 Codex / Claude Code 的 JSONL 会话日志，而是通过 hooks 实时接收事件。

## 架构

```text
Codex / Claude Code hooks
        ↓
hook_emit.py
        ↓
runtime/m5_ai_events.jsonl
        ↓
main.py
        ↓
state_controller.py
        ↓
serial_sender.py
        ↓
M5StickC Plus
```

## 文件职责

- `hook_emit.py`：Codex / Claude Code hook 入口，读取 stdin 中的 hook JSON，写入本地事件队列。
- `ai_event_detector.py`：读取 `runtime/m5_ai_events.jsonl`，输出统一事件。
- `state_controller.py`：把统一事件转换成开发板命令，处理优先级、去重和回到 `IDLE`。
- `serial_sender.py`：只负责串口自动识别、打开、发送、关闭。
- `config.py`：集中放波特率、轮询间隔、事件队列路径等配置。
- `main.py`：程序入口，读取 hook 事件队列，并根据状态控制结果发送串口命令。

## Hook 配置

项目内已提供：

```text
.codex/hooks.json
.claude/settings.json
```

Codex 需要在 `/hooks` 中审核并启用项目 hooks。Claude Code 会读取项目内 `.claude/settings.json`。

当前默认事件队列和调试日志放在项目内：

```text
codex_bridge_refactor/runtime/m5_ai_events.jsonl
codex_bridge_refactor/runtime/m5_hook_debug.log
```

## 调试

首次使用先在项目根目录同步 Python 环境：

```bash
uv sync
```

不接开发板时，用 debug 模式：

```bash
uv run python codex_bridge_refactor/main.py --debug
```

保持它运行，然后触发一次 Codex 工具调用。正常会看到：

```text
event codex: TOOL (PreToolUse)
serial command=TYPE debug=true
```


## 连接开发板

自动识别串口：

```bash
uv run python codex_bridge_refactor/main.py
```

手动指定串口：

```bash
uv run python codex_bridge_refactor/main.py --port /dev/cu.usbserial-0001 --source codex
uv run python codex_bridge_refactor/main.py --port COM5 --source codex
```

手动发送命令测试：

```bash
uv run python codex_bridge_refactor/main.py --port COM5 --send BEEP
uv run python codex_bridge_refactor/main.py --port COM5 --send THINK
```

串口发送只使用 `pyserial`。如果 `uv sync` 没有安装好依赖，或者端口名不正确，程序会直接报错退出，不会通过 `stty`、PowerShell 或普通文件写入兜底发送。

## 事件映射

| Hook 事件 | 统一事件 | 开发板命令 |
| --- | --- | --- |
| `UserPromptSubmit` | `WORKING` | `THINK` |
| `PreToolUse` | `TOOL` | `TYPE` |
| `PostToolUse` | `WORKING` | `THINK` |
| `PermissionRequest` | `WAITING` | `DONE` |
| `Notification` | `WAITING` / `SPEAKING` | `DONE` / `SPEAK` |
| `Stop` / `StopFailure` | `DONE` | `DONE` |
