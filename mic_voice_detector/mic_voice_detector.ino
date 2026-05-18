#include <M5StickCPlus.h>
#include <ESP_I2S.h>

static constexpr int MIC_CLK_PIN = 0;
static constexpr int MIC_DATA_PIN = 34;
static constexpr int SAMPLE_RATE = 44100;
static constexpr int SAMPLE_COUNT = 512;
static constexpr int VOICE_THRESHOLD = 900;

int16_t samples[SAMPLE_COUNT];
int lastBarWidth = -1;
bool lastVoice = false;
I2SClass MicI2S;

struct AudioStats {
  int rms;
  int peak;
  int minValue;
  int maxValue;
  size_t bytesRead;
  int readResult;
};

bool setupMic() {
  MicI2S.setPinsPdmRx(MIC_CLK_PIN, MIC_DATA_PIN);
  return MicI2S.begin(
      I2S_MODE_PDM_RX,
      SAMPLE_RATE,
      I2S_DATA_BIT_WIDTH_16BIT,
      I2S_SLOT_MODE_MONO);
}

AudioStats readAudioStats() {
  AudioStats stats = {0, 0, 0, 0, 0, 0};
  stats.bytesRead = MicI2S.readBytes((char *)samples, sizeof(samples));
  stats.readResult = MicI2S.lastError();

  if (stats.bytesRead == 0) {
    return stats;
  }

  const int count = stats.bytesRead / sizeof(samples[0]);
  int64_t sumSquares = 0;
  int32_t dc = 0;
  int16_t minValue = INT16_MAX;
  int16_t maxValue = INT16_MIN;

  for (int i = 0; i < count; ++i) {
    dc += samples[i];
    minValue = min(minValue, samples[i]);
    maxValue = max(maxValue, samples[i]);
  }
  dc /= count;

  for (int i = 0; i < count; ++i) {
    const int32_t centered = samples[i] - dc;
    sumSquares += (int64_t)centered * centered;
  }

  stats.rms = sqrt((double)sumSquares / count);
  stats.peak = maxValue - minValue;
  stats.minValue = minValue;
  stats.maxValue = maxValue;
  return stats;
}

void drawStaticUi() {
  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.setTextColor(WHITE, BLACK);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setCursor(10, 12);
  M5.Lcd.print("MIC TEST");
  M5.Lcd.drawRect(10, 125, 220, 9, WHITE);
}

void drawStatus(const AudioStats &stats) {
  const bool voice = stats.rms > VOICE_THRESHOLD;
  const int barWidth = constrain(map(stats.rms, 0, 5000, 0, 218), 0, 218);

  if (voice != lastVoice) {
    M5.Lcd.fillRect(10, 38, 150, 34, BLACK);
    lastVoice = voice;
  }
  M5.Lcd.setTextSize(2);
  M5.Lcd.setCursor(10, 44);
  M5.Lcd.setTextColor(voice ? GREEN : DARKGREY, BLACK);
  M5.Lcd.print(voice ? "VOICE" : "QUIET");

  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(WHITE, BLACK);
  M5.Lcd.fillRect(10, 76, 220, 46, BLACK);
  M5.Lcd.setCursor(10, 76);
  M5.Lcd.printf("RMS:%d  PK:%d", stats.rms, stats.peak);
  M5.Lcd.setCursor(10, 91);
  M5.Lcd.printf("bytes:%u  err:%d", (unsigned)stats.bytesRead, stats.readResult);
  M5.Lcd.setCursor(10, 106);
  M5.Lcd.printf("min:%d  max:%d", stats.minValue, stats.maxValue);

  if (barWidth != lastBarWidth) {
    M5.Lcd.fillRect(11, 126, 218, 7, BLACK);
    M5.Lcd.fillRect(11, 126, barWidth, 7, voice ? GREEN : BLUE);
    lastBarWidth = barWidth;
  }
}

void setup() {
  Serial.begin(115200);
  M5.begin();

  M5.Lcd.setRotation(1);
  drawStaticUi();

  const bool micReady = setupMic();
  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(micReady ? GREEN : RED, BLACK);
  M5.Lcd.setCursor(10, 32);
  M5.Lcd.printf("I2S init: %s", micReady ? "OK" : "FAIL");
  Serial.printf("I2S init: %s\n", micReady ? "OK" : "FAIL");
}

void loop() {
  M5.update();
  const AudioStats stats = readAudioStats();

  Serial.printf(
      "bytes=%u err=%d min=%d max=%d peak=%d rms=%d voice=%d\n",
      (unsigned)stats.bytesRead,
      stats.readResult,
      stats.minValue,
      stats.maxValue,
      stats.peak,
      stats.rms,
      stats.rms > VOICE_THRESHOLD);
  drawStatus(stats);

  delay(120);
}
