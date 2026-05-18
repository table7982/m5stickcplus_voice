# M5StickC Plus 1.1 Voice / Claude Bot Prototype

这个目录包含两个 M5StickC Plus 1.1 / ESP32-PICO-D4 原型：

- `mic_voice_detector/`: 板载麦克风测试程序。
- `claude_bot_pet/`: Cloudling / Codex 风格桌宠展示程序。

## 硬件结论

- 板子自带麦克风：SPM1423 PDM 数字麦克风。
- 板载麦克风引脚：CLK = GPIO0，DATA = GPIO34。
- 屏幕：1.14 inch 135x240 TFT，横屏后按 240x135 设计。
- 本机曾识别到的串口：COM5 Serial Port (USB)。

## Cloudling / Codex 桌宠程序

主程序：

```text
claude_bot_pet/claude_bot_pet.ino
```

GIF 转换帧资源：

```text
claude_bot_pet/cloudling_frames.h
```

功能：

- 参考 `clawd-on-desk` 里的 Cloudling / Codex GIF 素材，抽帧、去绿色背景、裁剪后缩放成 96x96 小屏帧。
- 程序播放时按 2x 放大到 192x192，并按屏幕中心裁切；由于 M5StickC Plus 屏幕只有 240x135，纵向会主动裁切一部分，让主体尽量大。
- `BtnA` 切到下一个状态。
- `BtnB` 切到上一个状态。
- 状态包括：
  - `IDLE`: 白色云朵本体、蓝紫眼睛、轻微呼吸和眨眼。
  - `THINK`: 云朵叠加圆形电路/思考覆盖层。
  - `TYPE`: 云朵显示 `/ +` 编码表情。
  - `BUILD`: 终端窗口形态，模拟构建输出。
  - `JUGGLE`: 云朵带光标/轨迹效果。
  - `SPARK`: 云朵带星光效果。
- 使用 `TFT_eSprite` 缓冲整帧画面，再推送到屏幕，避免直接整屏刷新造成闪烁。

说明：M5StickC Plus 的 Arduino 环境不能像网页一样直接播放 GIF 文件。本工程采用离线转换方案，把 GIF 的关键帧转成 `PROGMEM` 里的 RGB565 帧数据，烧录后不依赖额外 GIF 解码库。

烧录：

1. 打开 `claude_bot_pet/claude_bot_pet.ino`。
2. 开发板选择 `M5Stick-C-Plus` 或 `M5StickCPlus`。
3. 端口选择实际 USB 串口，例如 `COM5 Serial Port (USB)`。
4. 点击上传。

上传成功后通常会看到：

```text
Writing at ... 100.0%
Hash of data verified.
Hard resetting via RTS pin...
```

## 麦克风测试程序

主程序：

```text
mic_voice_detector/mic_voice_detector.ino
```

它会读取板载麦克风，计算声音强度，并在屏幕上显示：

- `VOICE` / `QUIET`
- `RMS`
- `PK`
- `bytes`
- `err`
- `min/max`
- 音量条

这不是完整语音识别模型，而是语音系统的第一步：确认麦克风、采样、屏幕和串口都正常。

## Arduino IDE 环境

1. 安装 Arduino IDE。
2. 打开 `File -> Preferences`。
3. 在 `Additional boards manager URLs` 中加入：

```text
https://static-cdn.m5stack.com/resource/arduino/package_m5stack_index.json
```

4. 打开 `Boards Manager`，搜索并安装 `M5Stack`。
5. 打开 `Library Manager`，确认安装 `M5StickCPlus`。

## 本次踩坑记录

### 1. M5Stack 平台包下载失败

安装 `M5Stack 3.3.7` 时，Arduino IDE 可能会从 GitHub 下载依赖失败，例如：

```text
Failed to install platform: 'M5Stack:3.3.7'
Download failed: performing HEAD request
```

常见失败文件包括：

```text
esp32c3-libs-3.3.7.zip
esp32c5-libs-3.3.7.zip
esp32c6-libs-3.3.7.zip
esp32h2-libs-3.3.7.zip
esp32p4-libs-3.3.7.zip
esp32p4_es-libs-3.3.7.zip
esp32s2-libs-3.3.7.zip
esp32s3-libs-3.3.7.zip
```

解决办法：

- 优先换网络、开代理，或直接重试安装。
- 也可以手动下载失败的 zip 文件，放到 Arduino 缓存目录：

```text
C:\Users\<用户名>\AppData\Local\Arduino15\staging\packages
```

然后重新安装 `M5Stack` 平台包。

### 2. 找不到 M5StickCPlus.h

如果编译报错：

```text
fatal error: M5StickCPlus.h: No such file or directory
```

优先检查 Arduino IDE 的 `Sketchbook location`。

本机默认库目录是：

```text
C:\Users\23817\Documents\Arduino\libraries
```

`M5StickCPlus.h` 位于：

```text
C:\Users\23817\Documents\Arduino\libraries\M5StickCPlus\src\M5StickCPlus.h
```

如果把 `Sketchbook location` 改到了其他目录，Arduino IDE 就可能看不到这个库。恢复默认目录并重启 Arduino IDE 后再编译。

### 3. bytes 有值，但 RMS/PK/min/max 全是 0

现象：

```text
bytes = 1024
err = 0
RMS = 0
PK = 0
min = 0
max = 0
```

这说明 I2S DMA 读到了缓冲区，但音频数据全是 0。

原因是：在 `M5Stack 3.3.7 / Arduino-ESP32 3.x` 环境下，旧的 `driver/i2s.h` PDM 读取方式容易读出全零数据。

最终解决办法是改用 Arduino-ESP32 3.x 自带的新版 `ESP_I2S`：

```cpp
#include <ESP_I2S.h>

I2SClass MicI2S;

MicI2S.setPinsPdmRx(0, 34);
MicI2S.begin(
    I2S_MODE_PDM_RX,
    44100,
    I2S_DATA_BIT_WIDTH_16BIT,
    I2S_SLOT_MODE_MONO);
```

读取时使用：

```cpp
MicI2S.readBytes((char *)samples, sizeof(samples));
```

这版已经验证可用，拍手和说话时 `RMS/PK/min/max` 会变化。

### 4. 屏幕一直闪

原因是每次循环都直接整屏刷新：

```cpp
M5.Lcd.fillScreen(BLACK);
```

解决办法：

- 简单 UI：只刷新变化区域。
- 动画 UI：使用 `TFT_eSprite` 先在内存中画完整帧，再 `pushSprite()` 到屏幕。

当前桌宠程序使用的是 `TFT_eSprite` 方案。

### 5. BEEP 命令收到但没有声音

现象：

```text
python codex_m5_bridge.py --port COM5 --send BEEP
```

屏幕底部 `RX:BEEP` 闪了一下，但蜂鸣器没有声音。

原因：`M5StickCPlus` 老库里的 `M5.Beep` 对 Arduino-ESP32 3.x 不完全兼容。ESP32 3.x 的 `ledcWriteTone()` 参数是 `pin`，老库仍按旧写法传 `TONE_PIN_CHANNEL`，会导致 tone 写到错误目标。

解决办法：桌宠程序绕开 `M5.Beep`，直接对 `SPEAKER_PIN` 做 LEDC 输出：

```cpp
ledcAttach(SPEAKER_PIN, 4000, 13);
ledcWriteTone(SPEAKER_PIN, frequency);
```

当前 `claude_bot_pet.ino` 已经按这个方式处理。

## 后续方向

1. 通过 USB 串口接入电脑端状态：电脑发送 `idle` / `working`，板子切换桌宠状态。
2. 用麦克风检测有人说话，触发临时动画状态。
3. 用 Edge Impulse 训练少量离线关键词，比如“打开”“关闭”“下一页”。
4. 在线语音识别：M5StickC Plus 负责采音和显示，把音频通过 Wi-Fi 发给电脑、服务器或 OpenAI API 识别。
