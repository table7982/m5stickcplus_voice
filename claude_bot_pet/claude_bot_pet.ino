#include <M5StickCPlus.h>
#include "utility/Config.h"

#include "cloudling_frames.h"

static constexpr int SCREEN_W = 240;
static constexpr int SCREEN_H = 135;
static constexpr int FRAME_SCALE = 2;
static constexpr int SCALED_FRAME_W = CLOUDLING_FRAME_W * FRAME_SCALE;
static constexpr int SCALED_FRAME_H = CLOUDLING_FRAME_H * FRAME_SCALE;
static constexpr int FRAME_X = (SCREEN_W - SCALED_FRAME_W) / 2;
static constexpr int FRAME_Y = (SCREEN_H - SCALED_FRAME_H) / 2;

TFT_eSprite canvas = TFT_eSprite(&M5.Lcd);

uint8_t currentAnim = 0;
uint8_t currentFrame = 0;
uint32_t lastFrameTick = 0;
bool needsRedraw = true;
String serialLine;
String lastCommand = "IDLE";

struct BeepStep {
  uint16_t frequency;
  uint16_t durationMs;
};

static const BeepStep DONE_BEEP[] = {
    {3136, 180},
    {0, 60},
    {3951, 220},
    {0, 70},
    {5274, 260},
};

bool beepPlaying = false;
uint8_t beepIndex = 0;
uint32_t beepStepStartedAt = 0;

uint16_t bgColor;
uint16_t panelColor;
uint16_t textColor;
uint16_t accentColor;
uint16_t mutedColor;

void initPalette() {
  bgColor = canvas.color565(12, 17, 28);
  panelColor = canvas.color565(21, 30, 49);
  textColor = canvas.color565(236, 242, 255);
  accentColor = canvas.color565(132, 207, 255);
  mutedColor = canvas.color565(121, 140, 172);
}

void setupBeeper() {
#if ESP_IDF_VERSION_MAJOR > 4
  ledcAttach(SPEAKER_PIN, 4000, 13);
#else
  ledcSetup(TONE_PIN_CHANNEL, 4000, 13);
  ledcAttachPin(SPEAKER_PIN, TONE_PIN_CHANNEL);
#endif
}

void toneOn(uint16_t frequency) {
#if ESP_IDF_VERSION_MAJOR > 4
  ledcWriteTone(SPEAKER_PIN, frequency);
#else
  ledcWriteTone(TONE_PIN_CHANNEL, frequency);
#endif
}

void toneOff() {
  toneOn(0);
  digitalWrite(SPEAKER_PIN, LOW);
}

CloudlingAnim getAnim(uint8_t index) {
  CloudlingAnim anim;
  memcpy_P(&anim, &CLOUDLING_ANIMS[index], sizeof(anim));
  return anim;
}

CloudlingFrame getFrame(const CloudlingAnim &anim, uint8_t frameIndex) {
  CloudlingFrame frame;
  memcpy_P(&frame, &anim.frames[frameIndex], sizeof(frame));
  return frame;
}

void drawStatusBar(const CloudlingAnim &anim) {
  canvas.fillRoundRect(8, 109, 75, 20, 5, panelColor);
  canvas.setTextSize(1);
  canvas.setTextColor(accentColor, panelColor);
  canvas.setCursor(18, 116);
  canvas.print(anim.label);

  canvas.setTextColor(mutedColor, bgColor);
  canvas.setCursor(96, 116);
  canvas.print("RX:");
  canvas.print(lastCommand.substring(0, 8));
}

void drawCloudlingFrame(const CloudlingFrame &frame, int x0, int y0) {
  for (uint16_t spanIndex = 0; spanIndex < frame.spanCount; ++spanIndex) {
    CloudlingSpan span;
    memcpy_P(&span, &frame.spans[spanIndex], sizeof(span));

    for (uint8_t i = 0; i < span.len; ++i) {
      const uint16_t color = pgm_read_word(&frame.colors[span.offset + i]);
      const int px = x0 + (span.x + i) * FRAME_SCALE;
      const int py = y0 + span.y * FRAME_SCALE;
      if (px >= SCREEN_W || py >= SCREEN_H || px + FRAME_SCALE <= 0 || py + FRAME_SCALE <= 0) {
        continue;
      }
      canvas.fillRect(px, py, FRAME_SCALE, FRAME_SCALE, color);
    }
  }
}

void drawCurrentFrame() {
  const CloudlingAnim anim = getAnim(currentAnim);
  const CloudlingFrame frame = getFrame(anim, currentFrame);

  canvas.fillSprite(bgColor);
  drawStatusBar(anim);
  drawCloudlingFrame(frame, FRAME_X, FRAME_Y);
  canvas.pushSprite(0, 0);
}

void setAnim(uint8_t nextAnim) {
  nextAnim = nextAnim % CLOUDLING_ANIM_COUNT;
  if (currentAnim == nextAnim) {
    return;
  }
  currentAnim = nextAnim;
  currentFrame = 0;
  lastFrameTick = millis();
  needsRedraw = true;
}

void startDoneBeep() {
  beepPlaying = true;
  beepIndex = 0;
  beepStepStartedAt = millis();
  toneOn(DONE_BEEP[0].frequency);
}

void updateBeep() {
  if (!beepPlaying) {
    return;
  }

  const uint32_t now = millis();
  if (now - beepStepStartedAt < DONE_BEEP[beepIndex].durationMs) {
    return;
  }

  beepIndex++;
  if (beepIndex >= sizeof(DONE_BEEP) / sizeof(DONE_BEEP[0])) {
    beepPlaying = false;
    toneOff();
    return;
  }

  beepStepStartedAt = now;
  if (DONE_BEEP[beepIndex].frequency == 0) {
    toneOff();
  } else {
    toneOn(DONE_BEEP[beepIndex].frequency);
  }
}

void applyCommand(String command) {
  command.trim();
  command.toUpperCase();
  lastCommand = command;
  needsRedraw = true;

  if (command == "IDLE") {
    setAnim(0);
  } else if (command == "THINK" || command == "THINKING") {
    setAnim(1);
  } else if (command == "TYPE" || command == "TYPING") {
    setAnim(2);
  } else if (command == "BUILD" || command == "BUILDING") {
    setAnim(3);
  } else if (command == "JUGGLE") {
    setAnim(4);
  } else if (command == "SPARK" || command == "SPEAK" || command == "OUTPUT") {
    setAnim(5);
  } else if (command == "DONE" || command == "COMPLETE" || command == "FINISH") {
    setAnim(0);
    startDoneBeep();
  } else if (command == "BEEP") {
    startDoneBeep();
  }
}

void handleSerial() {
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialLine.length() > 0) {
        applyCommand(serialLine);
        serialLine = "";
      }
    } else if (serialLine.length() < 32) {
      serialLine += c;
    }
  }
}

void handleButtons() {
  if (M5.BtnA.wasPressed()) {
    setAnim((currentAnim + 1) % CLOUDLING_ANIM_COUNT);
  }

  if (M5.BtnB.wasPressed()) {
    setAnim((currentAnim + CLOUDLING_ANIM_COUNT - 1) % CLOUDLING_ANIM_COUNT);
  }
}

void updateAnimation() {
  const CloudlingAnim anim = getAnim(currentAnim);
  const uint32_t now = millis();

  if (needsRedraw || now - lastFrameTick >= anim.frameMs) {
    if (!needsRedraw) {
      currentFrame = (currentFrame + 1) % anim.frameCount;
    }
    lastFrameTick = now;
    needsRedraw = false;
    drawCurrentFrame();
  }
}

void setup() {
  Serial.begin(115200);
  M5.begin();
  M5.Lcd.setRotation(1);
  M5.Lcd.fillScreen(BLACK);
  setupBeeper();

  canvas.setColorDepth(16);
  canvas.createSprite(SCREEN_W, SCREEN_H);
  initPalette();
  drawCurrentFrame();
}

void loop() {
  M5.update();
  handleSerial();
  handleButtons();
  updateBeep();
  updateAnimation();
  delay(10);
}
