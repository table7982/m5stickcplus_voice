# Codex to M5StickC Plus Bridge

This bridge watches local Codex JSONL session logs and sends simple state
commands to the M5StickC Plus over USB serial.

It is designed to work on Windows and macOS without requiring Codex hooks.

## Commands Sent To The Board

```text
THINK
TYPE
SPEAK
IDLE
DONE
```

- `THINK`: Codex is producing reasoning/model output.
- `TYPE`: Codex is running tools, applying patches, or emitting code-like work.
- `SPEAK`: Codex is writing a visible assistant message/final response.
- `DONE`: Codex finished a task. The board returns to `IDLE` and beeps.
- `IDLE`: No active Codex activity for a short timeout.

The bridge is a low-latency log tailer:

- It polls the active JSONL file every 50 ms.
- It rescans for a newer Codex session every 1.5 seconds.
- It keeps the current non-idle state for up to 18 seconds without new activity, so brief pauses do not flicker back to `IDLE`.
- Within a batch of new log lines, priority is `DONE > TYPE > SPEAK > THINK > IDLE`.

## Board Setup

Upload:

```text
../claude_bot_pet/claude_bot_pet.ino
```

The sketch listens at `115200` baud.

## Run With Anaconda Python

If you use Anaconda, open **Anaconda Prompt** or a terminal where `conda` is active.

Optional but recommended:

```bash
conda install pyserial
```

or:

```bash
pip install pyserial
```

Then run the bridge.

Windows:

```powershell
python codex_m5_bridge.py --port COM5
```

macOS:

```bash
python3 codex_m5_bridge.py --port /dev/cu.usbserial-0001
```

Auto-detect can also work:

```bash
python3 codex_m5_bridge.py
```

If the bridge watches the wrong Codex session, bind it to a specific JSONL file:

```bash
python3 codex_m5_bridge.py --port COM5 --session "C:\Users\23817\.codex\sessions\2026\05\17\rollout-....jsonl"
```

Manual test:

```bash
python3 codex_m5_bridge.py --port COM5 --send THINK
python3 codex_m5_bridge.py --port COM5 --send TYPE
python3 codex_m5_bridge.py --port COM5 --send SPEAK
python3 codex_m5_bridge.py --port COM5 --send DONE
python3 codex_m5_bridge.py --port COM5 --send BEEP
```

The board displays the last received command as `RX:<command>` at the bottom.
If the animation changes but there is no sound, test `--send BEEP`.
If `RX:DONE` never appears after a Codex task finishes, run:

```bash
python3 codex_m5_bridge.py --port COM5 --debug
```

and check whether events are being detected as `THINK`, `TYPE`, `SPEAK`, and `DONE`.

After editing this script, stop the running bridge with `Ctrl+C` and start it
again. A running Python process will not pick up code changes automatically.

## Notes

- On Windows, the script uses PowerShell/.NET `System.IO.Ports.SerialPort`.
- On macOS/Linux, it configures the serial device with `stty` and writes to the device file.
- If `pyserial` is installed, the script uses it automatically on any platform.
- With Anaconda, installing `pyserial` is recommended because it gives the most stable serial connection.
- Codex log formats can change. The bridge uses broad event heuristics instead of depending on one exact schema.
