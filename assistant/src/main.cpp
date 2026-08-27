#include <Arduino.h>
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <WiFiUdp.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <math.h>

#include "secrets.h"

#ifndef HA_LAMP1_ENTITY
#define HA_LAMP1_ENTITY "light.lamp_one"
#endif
#ifndef HA_LAMP2_ENTITY
#define HA_LAMP2_ENTITY "light.lamp_two"
#endif

// ============================================================================
// HARDWARE PIN DEFINITIONS & HARDWARE CONSTANTS
// ============================================================================

// MAX98357A I2S Class D Amplifier (Speaker)
#define I2S_SPK_BCLK    17
#define I2S_SPK_LRC     18
#define I2S_SPK_DIN     8
#define SPK_SAMPLE_RATE 16000 // 16kHz clean I2S master clock

// INMP441 I2S MEMS Microphone
#define I2S_MIC_SCK     15
#define I2S_MIC_WS      16
#define I2S_MIC_SD      7
#define MIC_SAMPLE_RATE 16000

// Hardware BOOT Button (GPIO 0)
#define BTN_BOOT        0

// Govee Local UDP Port
#define GOVEE_UDP_PORT  4003

// Fast Audio Buffers & Low-Latency Timing
#define PREROLL_SAMPLES     3200                       // 200ms pre-roll buffer @ 16kHz
#define MAX_RECORD_SAMPLES  (MIC_SAMPLE_RATE * 24 / 10) // 2.4s max capture window
#define MIN_RECORD_SAMPLES  (MIC_SAMPLE_RATE * 9 / 10)  // 0.9s minimum capture for ultra-snappy response
#define VAD_SILENCE_FRAMES  16                         // ~340ms silence cutoff

// ============================================================================
// DATA STRUCTURES & STATE MACHINE
// ============================================================================

enum AudioCommandType {
  CMD_NONE,
  CMD_STARTUP,
  CMD_WAKE,
  CMD_COIN,
  CMD_CHIME,
  CMD_POWERDOWN,
  CMD_ERROR,
  CMD_STOP
};

struct AudioCommand {
  AudioCommandType type;
};

struct VoiceRecordMsg {
  int16_t* pcmData;
  size_t sampleCount;
  bool isManualTrigger;
};

struct SmartHomeResult {
  bool handled;
  bool success;
  String action;
  String target;
  String message;
};

enum AssistantState {
  STATE_IDLE_WAIT_WAKE,
  STATE_LISTENING_FOR_COMMAND
};

// FreeRTOS Queues and Handles
QueueHandle_t audioQueue = NULL;
QueueHandle_t voiceQueue = NULL;
TaskHandle_t micTaskHandle = NULL;
TaskHandle_t voiceTaskHandle = NULL;
TaskHandle_t audioTaskHandle = NULL;

// Audio capture & Pre-roll buffer
int16_t* speechBuffer = NULL;
int16_t preRollBuffer[PREROLL_SAMPLES];
size_t preRollIndex = 0;
volatile bool isRecordingVoice = false;
volatile bool isTranscribing = false;
volatile bool manualRecordRequested = false;

// Assistant State Machine & Tuned Audio Parameters
volatile AssistantState assistantState = STATE_IDLE_WAIT_WAKE;
volatile bool isSpeakerPlaying = false;
unsigned long commandWindowExpiry = 0;
float systemVolume = 0.45f; // 45% default volume (crisp, pleasant, and audible)
float micGain = 3.5f;       // 3.5x digital vocal pre-amplifier (enables speaking at 1-3m distance)
int vadThreshold = 750;     // Sensitive speech threshold for normal room distance
float liveMicRMS = 0.0f;
float liveMicPeak = 0.0f;
String lastTranscript = "";
String lastActionStatus = "Ready — Listening for 'Hey Burden'";
bool lightsCurrentState = false;

// Networking
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");
WiFiUDP udp;

// Forward Declarations
void handleSerialCommand(char c);
bool executeLightAction(bool turnOn, const String& targetName = "all");

// ============================================================================
// I2S HARDWARE DRIVERS (BUILT FROM SCRATCH FOR FLAWLESS STABILITY)
// ============================================================================

void initSpeakerI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SPK_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_MSB,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SPK_BCLK,
    .ws_io_num = I2S_SPK_LRC,
    .data_out_num = I2S_SPK_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_zero_dma_buffer(I2S_NUM_0);
  Serial.println("[HARDWARE] MAX98357A I2S Speaker DAC initialized on I2S_NUM_0 (Pins: BCLK=17, LRC=18, DIN=8)");
}

void initMicrophoneI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = MIC_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, // INMP441 outputs 24-bit in 32-bit slot
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_MIC_SCK,
    .ws_io_num = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_MIC_SD
  };

  i2s_driver_install(I2S_NUM_1, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pin_config);
  i2s_zero_dma_buffer(I2S_NUM_1);
  Serial.println("[HARDWARE] INMP441 I2S Microphone initialized on I2S_NUM_1 (Pins: SCK=15, WS=16, SD=7)");
}

// ============================================================================
// CLEAN DIGITAL AUDIO SYNTHESIZER (ZERO TEARING, ZERO STATIC, SMOOTH RAMPS)
// ============================================================================

void playToneClean(float freqHz, int durationMs, float toneVol = 1.0f) {
  if (freqHz <= 0.0f || systemVolume <= 0.005f) {
    vTaskDelay(pdMS_TO_TICKS(durationMs));
    return;
  }

  unsigned long tStart = millis();
  const int totalSamples = (SPK_SAMPLE_RATE * durationMs) / 1000;
  const int CHUNK_SIZE = 128;
  int16_t pcmBuffer[CHUNK_SIZE * 2]; // Stereo (Left + Right)

  float phase = 0.0f;
  float phaseStep = (2.0f * (float)M_PI * freqHz) / (float)SPK_SAMPLE_RATE;
  
  // Clean volume amplitude: max 24000 (prevents DAC saturation/tearing)
  float effectiveAmp = 24000.0f * systemVolume * toneVol;

  int samplesRemaining = totalSamples;
  size_t totalBytesWritten = 0;
  int writeErrors = 0;

  while (samplesRemaining > 0) {
    int chunk = (samplesRemaining > CHUNK_SIZE) ? CHUNK_SIZE : samplesRemaining;
    for (int i = 0; i < chunk; i++) {
      int sampleIdx = totalSamples - samplesRemaining + i;
      // 40-sample smooth raised-cosine window at onset and offset to eliminate clicks/static
      float envelope = 1.0f;
      if (sampleIdx < 40) {
        envelope = 0.5f * (1.0f - cosf((float)sampleIdx * (float)M_PI / 40.0f));
      } else if (sampleIdx > totalSamples - 40) {
        envelope = 0.5f * (1.0f - cosf((float)(totalSamples - sampleIdx) * (float)M_PI / 40.0f));
      }

      int16_t val = (int16_t)(sinf(phase) * effectiveAmp * envelope);
      pcmBuffer[i * 2]     = val; // Left channel (MAX98357A)
      pcmBuffer[i * 2 + 1] = val; // Right channel

      phase += phaseStep;
      if (phase >= 2.0f * (float)M_PI) phase -= 2.0f * (float)M_PI;
    }

    size_t bytesWritten = 0;
    esp_err_t err = i2s_write(I2S_NUM_0, pcmBuffer, chunk * 2 * sizeof(int16_t), &bytesWritten, pdMS_TO_TICKS(100));
    if (err != ESP_OK || bytesWritten == 0) {
      writeErrors++;
    }
    totalBytesWritten += bytesWritten;
    samplesRemaining -= chunk;
  }

  // Smoothly drain DMA buffer with 64 samples of silence (prevents FIFO truncation)
  memset(pcmBuffer, 0, 64 * 2 * sizeof(int16_t));
  size_t drainBytes = 0;
  i2s_write(I2S_NUM_0, pcmBuffer, 64 * 2 * sizeof(int16_t), &drainBytes, pdMS_TO_TICKS(50));

  unsigned long elapsed = millis() - tStart;
  Serial.printf("[I2S SPK DEBUG] Tone %.1fHz (%dms target) -> wrote %u bytes in %lums (errors: %d | vol: %d%%)\n",
                freqHz, durationMs, (unsigned int)totalBytesWritten, elapsed, writeErrors, (int)(systemVolume * 100));
}

// Forward declarations for sound playback
void playStartupSound();
void playWakeChime();
void playCoinSound();
void playPowerdownSound();
void playErrorSound();

void runHardwareAudioDiagnostic() {
  Serial.println("\n========================================================");
  Serial.println("  🔬 ESP32-S3 HARDWARE AUDIO DIAGNOSTIC REPORT");
  Serial.println("========================================================");
  Serial.printf("  [HEAP] Free Internal DRAM: %u bytes | Lowest Free: %u bytes\n",
                ESP.getFreeHeap(), ESP.getMinFreeHeap());
  Serial.printf("  [CHIP] Model: ESP32-S3 | Cores: %d | CPU Freq: %d MHz\n",
                ESP.getChipCores(), ESP.getCpuFreqMHz());
  Serial.printf("  [AUDIO QUEUE] Pending messages: %d\n",
                uxQueueMessagesWaiting(audioQueue));
  Serial.printf("  [AUDIO CONFIG] Speaker Port: I2S_NUM_0 | Rate: %d Hz | Vol: %d%%\n",
                SPK_SAMPLE_RATE, (int)(systemVolume * 100));
  Serial.printf("  [PINS] MAX98357A -> BCLK=%d, LRC=%d, DIN=%d\n",
                I2S_SPK_BCLK, I2S_SPK_LRC, I2S_SPK_DIN);
  Serial.printf("  [MIC] INMP441 -> SCK=%d, WS=%d, SD=%d | Live RMS: %.1f | Peak: %.1f\n",
                I2S_MIC_SCK, I2S_MIC_WS, I2S_MIC_SD, liveMicRMS, liveMicPeak);
  Serial.println("--------------------------------------------------------");
  Serial.println("  [TEST 1/3] Generating Pure 440Hz Sine Wave (500ms)...");
  playToneClean(440.0f, 500, 1.0f);
  vTaskDelay(pdMS_TO_TICKS(100));
  
  Serial.println("  [TEST 2/3] Generating Ascending Scale (C5 -> E5 -> G5 -> C6)...");
  playStartupSound();
  vTaskDelay(pdMS_TO_TICKS(100));

  Serial.println("  [TEST 3/3] Generating Two-Tone Wake Ding (E5 -> A5)...");
  playWakeChime();

  Serial.println("========================================================\n");
}

void playStartupSound() {
  playToneClean(523.25f, 90, 0.9f); // C5
  vTaskDelay(pdMS_TO_TICKS(10));
  playToneClean(659.25f, 90, 0.9f); // E5
  vTaskDelay(pdMS_TO_TICKS(10));
  playToneClean(783.99f, 90, 0.95f); // G5
  vTaskDelay(pdMS_TO_TICKS(10));
  playToneClean(1046.50f, 220, 1.0f); // C6
}

void playWakeChime() {
  playToneClean(659.25f, 80, 0.95f); // E5
  vTaskDelay(pdMS_TO_TICKS(10));
  playToneClean(880.00f, 150, 1.0f); // A5
}

void playCoinSound() {
  playToneClean(987.77f, 70, 0.95f);  // B5
  vTaskDelay(pdMS_TO_TICKS(10));
  playToneClean(1318.51f, 280, 1.0f); // E6
}

void playPowerdownSound() {
  playToneClean(783.99f, 80, 0.95f); // G5
  vTaskDelay(pdMS_TO_TICKS(10));
  playToneClean(659.25f, 80, 0.9f);  // E5
  vTaskDelay(pdMS_TO_TICKS(10));
  playToneClean(523.25f, 180, 0.85f); // C5
}

void playErrorSound() {
  playToneClean(220.0f, 100, 0.9f);
  vTaskDelay(pdMS_TO_TICKS(15));
  playToneClean(180.0f, 180, 0.9f);
}

void audioTaskFunction(void* param) {
  AudioCommand cmd;
  for (;;) {
    if (xQueueReceive(audioQueue, &cmd, portMAX_DELAY) == pdTRUE) {
      isSpeakerPlaying = true;
      switch (cmd.type) {
        case CMD_STARTUP:
          playStartupSound();
          break;
        case CMD_WAKE:
          playWakeChime();
          break;
        case CMD_COIN:
          playCoinSound();
          break;
        case CMD_CHIME:
          playWakeChime();
          break;
        case CMD_POWERDOWN:
          playPowerdownSound();
          break;
        case CMD_ERROR:
          playErrorSound();
          break;
        case CMD_STOP:
          break;
        default:
          break;
      }
      isSpeakerPlaying = false;
      // If we just played the wake chime, now trigger microphone capture cleanly!
      if (cmd.type == CMD_WAKE && assistantState == STATE_LISTENING_FOR_COMMAND) {
        manualRecordRequested = true;
      }
    }
  }
}

// ============================================================================
// DIRECT HARDWARE & HOME ASSISTANT LIGHT CONTROL
// ============================================================================

bool sendGoveeLocalUdpCommand(const char* ipStr, bool turnOn) {
  IPAddress targetIP;
  if (!targetIP.fromString(ipStr)) return false;

  char jsonBuf[128];
  snprintf(jsonBuf, sizeof(jsonBuf),
           "{\"msg\":{\"cmd\":\"turn\",\"data\":{\"value\":%d}}}",
           turnOn ? 1 : 0);

  udp.beginPacket(targetIP, GOVEE_UDP_PORT);
  udp.write((const uint8_t*)jsonBuf, strlen(jsonBuf));
  bool ok = udp.endPacket();

  Serial.printf("[GOVEE UDP] Sent %s to %s:%d -> %s\n",
                turnOn ? "ON" : "OFF", ipStr, GOVEE_UDP_PORT, ok ? "SUCCESS" : "FAILED");
  return ok;
}

bool sendHomeAssistantLightCommand(const char* action, const char* entityId) {
  WiFiClient client;
  HTTPClient http;
  String url = String("http://") + HA_SERVER_IP + ":" + String(HA_SERVER_PORT) + "/api/services/light/" + action;

  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  if (strlen(HA_API_TOKEN) > 0) {
    http.addHeader("Authorization", String("Bearer ") + HA_API_TOKEN);
  }
  http.setTimeout(3000);

  String payload = "{\"entity_id\":\"" + String(entityId) + "\"}";
  int httpCode = http.POST(payload);
  bool success = (httpCode >= 200 && httpCode < 300);
  http.end();

  Serial.printf("[HA REST] %s on %s -> HTTP %d (%s)\n", action, entityId, httpCode, success ? "OK" : "ERR");
  return success;
}

bool executeLightAction(bool turnOn, const String& targetName) {
  lightsCurrentState = turnOn;

  // 1. Send direct Govee UDP commands for sub-5ms latency
  bool g1 = sendGoveeLocalUdpCommand(GOVEE_LAMP1_IP, turnOn);
  bool g2 = sendGoveeLocalUdpCommand(GOVEE_LAMP2_IP, turnOn);

  // 2. Sync with Home Assistant
  const char* haAction = turnOn ? "turn_on" : "turn_off";
  String haTarget = "all_lamps";
  if (targetName.indexOf("1") >= 0 || targetName.indexOf("one") >= 0) {
    haTarget = HA_LAMP1_ENTITY;
  } else if (targetName.indexOf("2") >= 0 || targetName.indexOf("two") >= 0) {
    haTarget = HA_LAMP2_ENTITY;
  }
  sendHomeAssistantLightCommand(haAction, haTarget.c_str());

  return (g1 || g2);
}

// ============================================================================
// WYOMING WHISPER STT PROTOCOL CLIENT (With Domain Context Hint)
// ============================================================================

bool sendAudioToWhisper(int16_t* pcmData, size_t numSamples, String& outTranscript) {
  if (numSamples < 4000 || !pcmData) return false;

  unsigned long tStart = millis();
  Serial.printf("[WHISPER] Streaming %u samples (%.2fs) to %s:%d...\n",
                (unsigned int)numSamples, (float)numSamples / MIC_SAMPLE_RATE, HA_SERVER_IP, WHISPER_PORT);

  WiFiClient client;
  client.setTimeout(6000);
  if (!client.connect(HA_SERVER_IP, WHISPER_PORT)) {
    Serial.println("[WHISPER ERROR] Could not connect to Whisper TCP port 10300!");
    return false;
  }
  client.setNoDelay(true);

  // 1. Transcribe event with prompt context bias (greatly improves accent and intent recognition)
  client.print("{\"type\":\"transcribe\",\"data\":{\"language\":\"en\",\"prompt\":\"Hey Burden, Alexa, Hey Jarvis, Okay Nabu, lights on, lights off, turn on, turn off, lamp on, lamp off, toggle.\"}}\n");

  // 2. Audio start event
  client.print("{\"type\":\"audio-start\",\"data\":{\"rate\":16000,\"width\":2,\"channels\":1}}\n");

  // 3. Stream audio in 1024-sample atomic chunks (2048 bytes)
  const size_t CHUNK_SAMPLES = 1024;
  size_t offset = 0;
  while (offset < numSamples && client.connected()) {
    size_t count = (numSamples - offset > CHUNK_SAMPLES) ? CHUNK_SAMPLES : (numSamples - offset);
    size_t bytes = count * sizeof(int16_t);
    client.printf("{\"type\":\"audio-chunk\",\"data\":{\"rate\":16000,\"width\":2,\"channels\":1},\"payload_length\":%u}\n", (unsigned int)bytes);
    client.write((const uint8_t*)(pcmData + offset), bytes);
    offset += count;
  }

  // 4. Audio stop event
  client.print("{\"type\":\"audio-stop\",\"data\":{}}\n");
  client.flush();

  // 5. Read response
  unsigned long startWait = millis();
  while (client.connected() && (millis() - startWait < 8000)) {
    if (client.available()) {
      String line = client.readStringUntil('\n');
      line.trim();
      if (line.length() > 0) {
        JsonDocument doc;
        DeserializationError err = deserializeJson(doc, line);
        if (!err) {
          int dataLength = doc["data_length"] | 0;
          if (dataLength > 0 && dataLength < 2048) {
            char dataBuf[2048];
            size_t bytesRead = client.readBytes(dataBuf, dataLength);
            dataBuf[bytesRead] = '\0';
            JsonDocument payloadDoc;
            if (!deserializeJson(payloadDoc, dataBuf)) {
              if (payloadDoc["text"].is<const char*>()) {
                outTranscript = String((const char*)payloadDoc["text"]);
                outTranscript.trim();
                client.stop();
                unsigned long elapsed = millis() - tStart;
                if (outTranscript.length() > 0) {
                  Serial.printf("[WHISPER RESULT] \"%s\" (took %lums)\n", outTranscript.c_str(), elapsed);
                  return true;
                } else {
                  Serial.printf("[WHISPER RESULT] (Empty / Silence) (took %lums)\n", elapsed);
                  return false;
                }
              }
            }
          }
          if (doc["text"].is<const char*>()) {
            outTranscript = String((const char*)doc["text"]);
            outTranscript.trim();
            client.stop();
            unsigned long elapsed = millis() - tStart;
            if (outTranscript.length() > 0) {
              Serial.printf("[WHISPER RESULT] \"%s\" (took %lums)\n", outTranscript.c_str(), elapsed);
              return true;
            } else {
              Serial.printf("[WHISPER RESULT] (Empty / Silence) (took %lums)\n", elapsed);
              return false;
            }
          } else if (doc["data"]["text"].is<const char*>()) {
            outTranscript = String((const char*)doc["data"]["text"]);
            outTranscript.trim();
            client.stop();
            unsigned long elapsed = millis() - tStart;
            if (outTranscript.length() > 0) {
              Serial.printf("[WHISPER RESULT] \"%s\" (took %lums)\n", outTranscript.c_str(), elapsed);
              return true;
            } else {
              Serial.printf("[WHISPER RESULT] (Empty / Silence) (took %lums)\n", elapsed);
              return false;
            }
          }
        }
      }
    }
    delay(5);
  }
  client.stop();
  Serial.println("[WHISPER TIMEOUT] No transcript received");
  return false;
}

// ============================================================================
// ACCENT TOLERANCE & PHONETIC WAKE WORD MATCHING
// ============================================================================

bool containsWakeWord(const String& clean) {
  const char* variants[] = {
    "burden", "birden", "birdin", "birdie", "birdy", "borden", "bordon",
    "barden", "berden", "biden", "britain", "burton", "bruh", "birth",
    "haibirth", "habers", "haber", "curtain", "everything", "have a good",
    "purdon", "pardon", "bertin", "bourdon", "burdan", "assistant",
    "jarvis", "travis", "garbage",
    "alexa", "alex", "alyssa", "alexus", "lexa",
    "nabu", "navu", "ok nabu", "okay nabu", "ok navu"
  };
  for (const char* v : variants) {
    if (clean.indexOf(v) >= 0) return true;
  }
  return false;
}

String stripWakeWord(const String& clean) {
  String s = clean;
  const char* prefixes[] = {
    "hey burden", "hey birden", "hey birdin", "hey birdie", "hey birdy", "hey borden", "hey bordon", "hey barden", "hey berden", "hey biden", "hey britain", "hey bruh",
    "hi burden", "hi birden", "hi birdie", "ok burden", "okay burden", "ok birdie",
    "burden", "birden", "birdin", "birdie", "birdy", "borden", "bordon", "barden", "berden", "biden", "britain", "burton", "bruh", "haibirth", "habers", "haber", "curtain", "everything", "have a good", "purdon", "pardon",
    "hey assistant", "assistant",
    "hey jarvis", "hi jarvis", "ok jarvis", "okay jarvis", "jarvis", "travis", "garbage",
    "hey alexa", "hi alexa", "ok alexa", "okay alexa", "alexa", "alex", "alyssa", "alexus", "lexa",
    "hey nabu", "hi nabu", "ok nabu", "okay nabu", "nabu", "navu", "ok navu"
  };
  for (const char* p : prefixes) {
    if (s.startsWith(p)) {
      s = s.substring(strlen(p));
      s.trim();
      return s;
    }
  }
  return s;
}

// ============================================================================
// VOICE INTENT PARSER & TWO-STAGE STATE MACHINE
// ============================================================================

SmartHomeResult parseAndExecuteVoiceCommand(const String& rawText) {
  SmartHomeResult res;
  res.handled = false;
  res.success = false;
  res.action = "";
  res.target = "";
  res.message = "";

  String text = rawText;
  text.toLowerCase();
  text.trim();

  // Strip punctuation
  String clean = "";
  for (unsigned int i = 0; i < text.length(); i++) {
    char c = text[i];
    if (isalnum(c) || c == ' ') clean += c;
  }
  clean.trim();

  if (clean.length() == 0) return res;

  Serial.printf("[INTENT] Analyzing (State=%s): \"%s\"\n",
                (assistantState == STATE_LISTENING_FOR_COMMAND) ? "COMMAND_WAIT" : "IDLE_WAKE",
                clean.c_str());

  // -------------------------------------------------------------------------
  // 1. If currently IDLE (Waiting for Wake Word)
  // -------------------------------------------------------------------------
  if (assistantState == STATE_IDLE_WAIT_WAKE) {
    if (containsWakeWord(clean)) {
      String cmd = stripWakeWord(clean);

      // If user ONLY spoke the wake word ("Hey Burden", "Hey Birdie", "Hey Britain", etc.)
      if (cmd.length() == 0) {
        res.handled = true;
        res.success = true;
        res.action = "WAKE_WORD";
        res.target = "Burden";
        res.message = "Trigger recognized! Listening for command...";

        // INSTANT AUDIO FEEDBACK: Play Wake Chime
        AudioCommand audioCmd = { CMD_WAKE };
        xQueueSend(audioQueue, &audioCmd, 0);

        // Transition to dedicated Command Listening state
        assistantState = STATE_LISTENING_FOR_COMMAND;
        commandWindowExpiry = millis() + 5000; // 5-second command window

        // Immediately trigger microphone capture for command
        manualRecordRequested = true;
        return res;
      }

      // If user spoke Wake Word + Command in one single breath ("Hey birdie lights on", "curtain lights on")
      clean = cmd; // Fall through to command parser below
    } else {
      // Check if user directly said lights on/off without wake word
      bool directOn = (clean.indexOf("lights on") >= 0 || clean.indexOf("light on") >= 0 || clean.indexOf("likes on") >= 0 || clean.indexOf("light zone") >= 0);
      bool directOff = (clean.indexOf("lights off") >= 0 || clean.indexOf("light off") >= 0 || clean.indexOf("likes off") >= 0 || clean.indexOf("nights off") >= 0);
      if (!directOn && !directOff) {
        return res;
      }
    }
  }

  // -------------------------------------------------------------------------
  // 2. Command Parsing (When in Command State OR One-Shot Wake+Command)
  // -------------------------------------------------------------------------
  String cmd = clean;

  // Check Lights On / Off / Toggle intents (with accent & whisper variations)
  bool isTurnOn = (cmd.indexOf("turn on") >= 0 || cmd.indexOf("switch on") >= 0 ||
                   cmd.indexOf("lights on") >= 0 || cmd.indexOf("light on") >= 0 ||
                   cmd.indexOf("likes on") >= 0 || cmd.indexOf("like on") >= 0 ||
                   cmd.indexOf("light zone") >= 0 || cmd.indexOf("lights in") >= 0 ||
                   cmd.indexOf("night on") >= 0 || cmd.indexOf("nights on") >= 0 ||
                   cmd.indexOf("lamp on") >= 0 || cmd.indexOf("lamps on") >= 0 ||
                   cmd == "on" || cmd.startsWith("on ") || cmd.endsWith(" on"));
  bool isTurnOff = (cmd.indexOf("turn off") >= 0 || cmd.indexOf("switch off") >= 0 ||
                    cmd.indexOf("lights off") >= 0 || cmd.indexOf("light off") >= 0 ||
                    cmd.indexOf("likes off") >= 0 || cmd.indexOf("like off") >= 0 ||
                    cmd.indexOf("nights off") >= 0 || cmd.indexOf("night off") >= 0 ||
                    cmd.indexOf("lamp off") >= 0 || cmd.indexOf("lamps off") >= 0 ||
                    cmd == "off" || cmd.startsWith("off ") || cmd.endsWith(" off"));
  bool isToggle = (cmd.indexOf("toggle") >= 0 || cmd.indexOf("flip") >= 0);

  if (isTurnOn || isTurnOff || isToggle) {
    res.handled = true;
    String target = "all";
    if (cmd.indexOf("lamp 1") >= 0 || cmd.indexOf("lamp one") >= 0 || cmd.indexOf("first") >= 0) {
      target = "lamp 1";
    } else if (cmd.indexOf("lamp 2") >= 0 || cmd.indexOf("lamp two") >= 0 || cmd.indexOf("second") >= 0) {
      target = "lamp 2";
    }

    bool stateToSet = isTurnOn ? true : (isTurnOff ? false : !lightsCurrentState);
    bool ok = executeLightAction(stateToSet, target);
    res.success = ok;
    res.action = stateToSet ? "turn_on" : "turn_off";
    res.target = target;
    res.message = String(stateToSet ? "Turned ON " : "Turned OFF ") + target;

    // Trigger speaker feedback
    AudioCommand audioCmd = { stateToSet ? CMD_COIN : CMD_POWERDOWN };
    xQueueSend(audioQueue, &audioCmd, 0);

    // Reset state machine back to Idle waiting for wake word
    assistantState = STATE_IDLE_WAIT_WAKE;
    return res;
  }

  // Sound Test Intents
  if (cmd.indexOf("coin") >= 0) {
    AudioCommand audioCmd = { CMD_COIN };
    xQueueSend(audioQueue, &audioCmd, 0);
    res.handled = true; res.success = true; res.action = "COIN"; res.message = "Playing coin";
    assistantState = STATE_IDLE_WAIT_WAKE;
    return res;
  }
  if (cmd.indexOf("chime") >= 0) {
    AudioCommand audioCmd = { CMD_CHIME };
    xQueueSend(audioQueue, &audioCmd, 0);
    res.handled = true; res.success = true; res.action = "CHIME"; res.message = "Playing chime";
    assistantState = STATE_IDLE_WAIT_WAKE;
    return res;
  }

  // If in command state but command wasn't understood
  if (assistantState == STATE_LISTENING_FOR_COMMAND) {
    AudioCommand audioCmd = { CMD_ERROR };
    xQueueSend(audioQueue, &audioCmd, 0);
    assistantState = STATE_IDLE_WAIT_WAKE;
  }

  return res;
}

// ============================================================================
// DECOUPLED ASYNC VOICE & INTENT TASK (Core 1)
// ============================================================================

void voiceTaskFunction(void* param) {
  VoiceRecordMsg msg;
  for (;;) {
    if (xQueueReceive(voiceQueue, &msg, portMAX_DELAY) == pdTRUE) {
      isTranscribing = true;
      lastActionStatus = "Transcribing audio via Whisper STT...";
      Serial.println("[VOICE TASK] Audio received. Processing with Whisper STT...");

      String transcript = "";
      bool sttOk = sendAudioToWhisper(msg.pcmData, msg.sampleCount, transcript);

      if (sttOk && transcript.length() > 0) {
        lastTranscript = transcript;
        Serial.printf("[VOICE TASK] Heard: \"%s\"\n", transcript.c_str());

        SmartHomeResult res = parseAndExecuteVoiceCommand(transcript);
        if (res.handled) {
          lastActionStatus = res.message;
          Serial.printf("[VOICE TASK] Handled intent: %s | Result: %s\n", res.action.c_str(), res.success ? "SUCCESS" : "FAILED");
        } else {
          lastActionStatus = "Heard: \"" + transcript + "\" (Unrecognized command)";
          if (assistantState == STATE_LISTENING_FOR_COMMAND) {
            AudioCommand audioCmd = { CMD_ERROR };
            xQueueSend(audioQueue, &audioCmd, 0);
            assistantState = STATE_IDLE_WAIT_WAKE;
          }
        }
      } else {
        lastActionStatus = (assistantState == STATE_LISTENING_FOR_COMMAND) ? "No command speech recognized" : "Listening for 'Hey Burden'...";
        Serial.println("[VOICE TASK] No speech recognized by Whisper");
        if (assistantState == STATE_LISTENING_FOR_COMMAND && millis() > commandWindowExpiry) {
          assistantState = STATE_IDLE_WAIT_WAKE;
        }
      }

      isTranscribing = false;
      isRecordingVoice = false;
    }
  }
}

// ============================================================================
// INMP441 SAMPLING & VAD TASK (Core 0)
// ============================================================================

void micTaskFunction(void* param) {
  const size_t DMA_READ_SAMPLES = 256;
  int32_t rawBuffer[DMA_READ_SAMPLES];
  int16_t pcmChunk[DMA_READ_SAMPLES];

  // 75Hz IIR High-Pass Filter State (removes DC bias)
  float x_prev = 0.0f;
  float y_prev = 0.0f;
  const float alpha = 0.95f;

  int silenceCount = 0;
  size_t currentSampleCount = 0;

  for (;;) {
    size_t bytesRead = 0;
    esp_err_t err = i2s_read(I2S_NUM_1, rawBuffer, sizeof(rawBuffer), &bytesRead, pdMS_TO_TICKS(50));
    if (err != ESP_OK || bytesRead == 0) {
      vTaskDelay(pdMS_TO_TICKS(5));
      continue;
    }

    size_t samplesRead = bytesRead / sizeof(int32_t);
    double sumSquares = 0.0;
    float chunkPeak = 0.0f;

    for (size_t i = 0; i < samplesRead; i++) {
      // INMP441 is 24-bit MSB-aligned in 32-bit slot
      int32_t val32 = rawBuffer[i] >> 8;
      float sampleFloat = ((float)val32 / 256.0f) * micGain; // Apply digital vocal pre-amplifier (3.5x)

      // Apply 75Hz High-Pass Filter
      float filtered = alpha * (y_prev + sampleFloat - x_prev);
      x_prev = sampleFloat;
      y_prev = filtered;

      // Soft AGC Headroom compression (prevents harsh digital clipping when shouting/speaking close)
      if (filtered > 24000.0f) filtered = 24000.0f + (filtered - 24000.0f) * 0.30f;
      else if (filtered < -24000.0f) filtered = -24000.0f + (filtered + 24000.0f) * 0.30f;

      if (filtered > 32767.0f) filtered = 32767.0f;
      if (filtered < -32768.0f) filtered = -32768.0f;

      int16_t sample16 = (int16_t)filtered;
      pcmChunk[i] = sample16;

      // Maintain circular pre-roll buffer (stores previous 200ms of audio)
      preRollBuffer[preRollIndex] = sample16;
      preRollIndex = (preRollIndex + 1) % PREROLL_SAMPLES;

      sumSquares += (double)sample16 * (double)sample16;
      float absVal = fabsf((float)sample16);
      if (absVal > chunkPeak) chunkPeak = absVal;
    }

    float rms = sqrtf((float)(sumSquares / samplesRead));
    liveMicRMS = rms;
    liveMicPeak = chunkPeak;

    // Check manual record request from Web/Serial
    if (manualRecordRequested && !isRecordingVoice && !isTranscribing) {
      manualRecordRequested = false;
      isRecordingVoice = true;
      currentSampleCount = 0;
      silenceCount = 0;

      // Copy 200ms pre-roll buffer into speechBuffer so word onset is preserved
      if (speechBuffer) {
        for (size_t k = 0; k < PREROLL_SAMPLES; k++) {
          size_t srcIdx = (preRollIndex + k) % PREROLL_SAMPLES;
          speechBuffer[currentSampleCount++] = preRollBuffer[srcIdx];
        }
      }

      Serial.println("[MIC] Command capture started (listening for 'lights on/off')...");
    }

    // Voice Activity Detection (VAD) Logic
    if (!isRecordingVoice && !isTranscribing && !isSpeakerPlaying) {
      // Ignore VAD during startup settling and before Wi-Fi connects (first 4 seconds)
      if (millis() > 4000 && WiFi.status() == WL_CONNECTED) {
        if (rms > (float)vadThreshold) {
          isRecordingVoice = true;
          currentSampleCount = 0;
          silenceCount = 0;

          // Copy 200ms pre-roll buffer into speechBuffer so word onset is preserved
          if (speechBuffer) {
            for (size_t k = 0; k < PREROLL_SAMPLES; k++) {
              size_t srcIdx = (preRollIndex + k) % PREROLL_SAMPLES;
              speechBuffer[currentSampleCount++] = preRollBuffer[srcIdx];
            }
          }

          Serial.printf("[VAD TRIGGER] Speech detected! RMS: %.1f > Threshold: %d (Gain: %.1fx | State: %s)\n",
                        rms, vadThreshold, micGain, (assistantState == STATE_LISTENING_FOR_COMMAND) ? "COMMAND" : "WAKE");
        }
      }
    }

    // Accumulate samples during recording
    if (isRecordingVoice && speechBuffer) {
      for (size_t i = 0; i < samplesRead; i++) {
        if (currentSampleCount < MAX_RECORD_SAMPLES) {
          speechBuffer[currentSampleCount++] = pcmChunk[i];
        }
      }

      if (rms < (float)(vadThreshold * 0.70f)) {
        silenceCount++;
      } else {
        silenceCount = 0;
      }

      // Snappy cutoff: Stop as soon as speech + short silence is reached
      if ((silenceCount >= VAD_SILENCE_FRAMES && currentSampleCount >= MIN_RECORD_SAMPLES) ||
          currentSampleCount >= MAX_RECORD_SAMPLES) {
        Serial.printf("[MIC] Speech capture finished (%u samples, %.2fs). Dispatching to Whisper STT...\n",
                      (unsigned int)currentSampleCount, (float)currentSampleCount / MIC_SAMPLE_RATE);

        VoiceRecordMsg msg;
        msg.pcmData = speechBuffer;
        msg.sampleCount = currentSampleCount;
        msg.isManualTrigger = false;
        xQueueSend(voiceQueue, &msg, 0);

        isRecordingVoice = false;
        silenceCount = 0;
      }
    }
  }
}

// ============================================================================
// SERIAL CLI COMMAND HANDLER
// ============================================================================

void printHelpMenu() {
  Serial.println("\n========================================================");
  Serial.println("  🤖 ESP32-S3 VOICE ASSISTANT — INTERACTIVE CLI");
  Serial.println("========================================================");
  Serial.printf("  Speaker Volume: %d%% | Mic Pre-Amp Gain: %.1fx | VAD Threshold: %d\n",
                (int)(systemVolume * 100), micGain, vadThreshold);
  Serial.printf("  Assistant State: %s\n", (assistantState == STATE_LISTENING_FOR_COMMAND) ? "LISTENING FOR COMMAND" : "IDLE (WAITING FOR WAKE WORD)");
  Serial.println("--------------------------------------------------------");
  Serial.println("  1 / on      : Turn Lights ON (Govee UDP + HA REST + Coin Sound)");
  Serial.println("  0 / off     : Turn Lights OFF (Govee UDP + HA REST + Chime)");
  Serial.println("  t / toggle  : Toggle Lights State");
  Serial.println("  w / wake    : Simulate Wake Word (Plays ding & starts command capture)");
  Serial.println("  r / record  : Manually Trigger 2.4s Mic Capture & Whisper STT");
  Serial.println("  g / gain    : Cycle Mic Pre-Amp Gain (1.5x -> 2.5x -> 3.5x -> 5.0x)");
  Serial.println("  +           : Increase Speaker Volume (+5%)");
  Serial.println("  -           : Decrease Speaker Volume (-5%)");
  Serial.println("  s / sound   : Test Audio Speaker (Startup, Wake, Coin, Chime)");
  Serial.println("  d / diag    : Run Full Hardware Audio & DMA Latency Diagnostic");
  Serial.println("  m / mic     : Print Live Mic RMS & Peak Level");
  Serial.println("  ? / help    : Display this menu");
  Serial.println("========================================================\n");
}

void handleSerialCommand(char c) {
  switch (c) {
    case '1':
      Serial.println("[CLI] Command: Turn Lights ON");
      executeLightAction(true);
      { AudioCommand cmd = { CMD_COIN }; xQueueSend(audioQueue, &cmd, 0); }
      break;
    case '0':
      Serial.println("[CLI] Command: Turn Lights OFF");
      executeLightAction(false);
      { AudioCommand cmd = { CMD_POWERDOWN }; xQueueSend(audioQueue, &cmd, 0); }
      break;
    case 't':
    case 'T':
      Serial.printf("[CLI] Command: Toggle Lights (Current: %s)\n", lightsCurrentState ? "ON" : "OFF");
      executeLightAction(!lightsCurrentState);
      { AudioCommand cmd = { lightsCurrentState ? CMD_COIN : CMD_POWERDOWN }; xQueueSend(audioQueue, &cmd, 0); }
      break;
    case 'w':
    case 'W':
      Serial.println("[CLI] Command: Simulated Wake Word ('Hey Burden')");
      {
        AudioCommand cmd = { CMD_WAKE };
        xQueueSend(audioQueue, &cmd, 0);
        assistantState = STATE_LISTENING_FOR_COMMAND;
        commandWindowExpiry = millis() + 5000;
        manualRecordRequested = true;
      }
      break;
    case 'r':
    case 'R':
      Serial.println("[CLI] Command: Manual Mic Record & Transcribe Triggered");
      manualRecordRequested = true;
      break;
    case 'g':
    case 'G':
      if (micGain < 2.0f) micGain = 2.5f;
      else if (micGain < 3.0f) micGain = 3.5f;
      else if (micGain < 4.0f) micGain = 5.0f;
      else micGain = 1.5f;
      Serial.printf("[CLI] Mic Digital Pre-Amp Gain set to: %.1fx\n", micGain);
      break;
    case '+':
      systemVolume = min(1.0f, systemVolume + 0.05f);
      Serial.printf("[CLI] Volume increased to %d%%\n", (int)(systemVolume * 100));
      { AudioCommand cmd = { CMD_CHIME }; xQueueSend(audioQueue, &cmd, 0); }
      break;
    case '-':
      systemVolume = max(0.05f, systemVolume - 0.05f);
      Serial.printf("[CLI] Volume decreased to %d%%\n", (int)(systemVolume * 100));
      { AudioCommand cmd = { CMD_CHIME }; xQueueSend(audioQueue, &cmd, 0); }
      break;
    case 's':
    case 'S':
      Serial.println("[CLI] Testing Speaker Sounds...");
      {
        AudioCommand cmd = { CMD_STARTUP }; xQueueSend(audioQueue, &cmd, 0);
        vTaskDelay(pdMS_TO_TICKS(500));
        AudioCommand cmd2 = { CMD_COIN }; xQueueSend(audioQueue, &cmd2, 0);
      }
      break;
    case 'd':
    case 'D':
      runHardwareAudioDiagnostic();
      break;
    case 'm':
    case 'M':
      Serial.printf("[CLI] Mic Live -> RMS: %.1f | Peak: %.1f | Gain: %.1fx | VAD Threshold: %d\n",
                    liveMicRMS, liveMicPeak, micGain, vadThreshold);
      break;
    case '?':
      printHelpMenu();
      break;
    default:
      break;
  }
}

// ============================================================================
// WEB SERVER & WEBSOCKET DASHBOARD
// ============================================================================

const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ESP32-S3 Voice Assistant</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --primary: #38bdf8;
      --accent: #10b981;
      --danger: #ef4444;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 20px; display: flex; justify-content: center; }
    .container { max-width: 600px; width: 100%; display: flex; flex-direction: column; gap: 16px; }
    .card { background: var(--card-bg); border-radius: 12px; padding: 20px; border: 1px solid rgba(255,255,255,0.08); }
    h1 { font-size: 1.4rem; color: var(--primary); display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
    h2 { font-size: 1.1rem; color: var(--text); margin-bottom: 10px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
    button {
      padding: 12px 16px; border: none; border-radius: 8px; font-weight: 600; font-size: 0.95rem;
      cursor: pointer; transition: all 0.2s; color: white; display: flex; align-items: center; justify-content: center; gap: 6px;
    }
    .btn-on { background: #059669; }
    .btn-on:hover { background: #10b981; }
    .btn-off { background: #dc2626; }
    .btn-off:hover { background: #ef4444; }
    .btn-wake { background: #8b5cf6; width: 100%; padding: 14px; font-size: 1rem; }
    .btn-wake:hover { background: #7c3aed; }
    .btn-sec { background: #334155; }
    .btn-sec:hover { background: #475569; }
    .status-badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; background: #334155; color: var(--primary); font-weight: 600; }
    .state-badge { display: inline-block; padding: 6px 12px; border-radius: 8px; font-size: 0.9rem; font-weight: 700; background: #0284c7; color: white; margin-top: 6px; }
    .transcript-box { background: #0b0f19; border-radius: 8px; padding: 14px; min-height: 50px; font-size: 1.05rem; color: #38bdf8; border-left: 4px solid var(--primary); }
    .meter-container { background: #0b0f19; height: 16px; border-radius: 8px; overflow: hidden; margin-top: 8px; }
    .meter-bar { height: 100%; width: 0%; background: linear-gradient(90deg, #10b981, #f59e0b, #ef4444); transition: width 0.1s; }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>🤖 ESP32-S3 Voice Assistant <span class="status-badge" id="netStatus">Connected</span></h1>
      <p style="color:var(--text-muted); font-size:0.9rem;">Trigger: Say <b>"Hey Burden"</b> (or <i>"Hey Birdie"</i>) $\rightarrow$ hear chime $\rightarrow$ say <b>"lights on"</b> / <b>"lights off"</b></p>
      <div><span class="state-badge" id="stateBadge">Waiting for Wake Word</span></div>
    </div>

    <div class="card">
      <h2>💡 Smart Lights Control</h2>
      <div class="grid">
        <button class="btn-on" onclick="sendCmd('on')">💡 Lights ON</button>
        <button class="btn-off" onclick="sendCmd('off')">🌑 Lights OFF</button>
      </div>
      <div class="grid" style="margin-top:8px;">
        <button class="btn-sec" onclick="sendCmd('toggle')">🔄 Toggle Lights</button>
        <button class="btn-sec" onclick="sendCmd('sound')">🔊 Test Speaker</button>
      </div>
    </div>

    <div class="card">
      <h2>🔊 Volume & Mic Sensitivity</h2>
      <div class="grid">
        <button class="btn-sec" onclick="sendCmd('vol_down')">🔉 Volume -5% (<span id="volLabel">30%</span>)</button>
        <button class="btn-sec" onclick="sendCmd('vol_up')">🔊 Volume +5%</button>
      </div>
      <div class="grid" style="margin-top:8px;">
        <button class="btn-sec" onclick="sendCmd('gain')">🎙️ Pre-Amp Gain: <span id="gainLabel">3.5x</span></button>
        <button class="btn-wake" onclick="sendCmd('wake')">⚡ Wake Ding</button>
      </div>
    </div>

    <div class="card">
      <h2>🎙️ Live Mic Audio Level</h2>
      <div class="meter-container">
        <div class="meter-bar" id="vuBar"></div>
      </div>
    </div>

    <div class="card">
      <h2>📝 Live Transcript & Status</h2>
      <div class="transcript-box" id="transcriptDisplay">Waiting for speech...</div>
      <p style="font-size:0.85rem; color:var(--text-muted); margin-top:8px;" id="actionDisplay">Status: Ready</p>
    </div>
  </div>

  <script>
    let ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onmessage = (e) => {
      let d = JSON.parse(e.data);
      if (d.rms !== undefined) {
        let pct = Math.min(100, (d.rms / 6000) * 100);
        document.getElementById('vuBar').style.width = pct + '%';
      }
      if (d.transcript !== undefined) {
        document.getElementById('transcriptDisplay').innerText = d.transcript ? `"${d.transcript}"` : 'No speech recognized';
      }
      if (d.status !== undefined) {
        document.getElementById('actionDisplay').innerText = 'Status: ' + d.status;
      }
      if (d.vol !== undefined) {
        document.getElementById('volLabel').innerText = Math.round(d.vol * 100) + '%';
      }
      if (d.gain !== undefined) {
        document.getElementById('gainLabel').innerText = d.gain.toFixed(1) + 'x';
      }
      if (d.state !== undefined) {
        let badge = document.getElementById('stateBadge');
        if (d.state === 1) {
          badge.innerText = '🎙️ Listening for Command (Say "lights on/off")...';
          badge.style.background = '#8b5cf6';
        } else {
          badge.innerText = '👂 Listening for "Hey Burden"...';
          badge.style.background = '#0284c7';
        }
      }
    };
    ws.onclose = () => { document.getElementById('netStatus').innerText = 'Disconnected'; };
    function sendCmd(act) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: act }));
      }
    }
  </script>
</body>
</html>
)rawliteral";

void handleWebSocketMessage(void *arg, uint8_t *data, size_t len) {
  AwsFrameInfo *info = (AwsFrameInfo*)arg;
  if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) {
    data[len] = 0;
    JsonDocument doc;
    if (!deserializeJson(doc, (char*)data)) {
      const char* act = doc["action"] | "";
      if (strcmp(act, "on") == 0) handleSerialCommand('1');
      else if (strcmp(act, "off") == 0) handleSerialCommand('0');
      else if (strcmp(act, "toggle") == 0) handleSerialCommand('t');
      else if (strcmp(act, "wake") == 0) handleSerialCommand('w');
      else if (strcmp(act, "record") == 0) handleSerialCommand('r');
      else if (strcmp(act, "sound") == 0) handleSerialCommand('s');
      else if (strcmp(act, "gain") == 0) handleSerialCommand('g');
      else if (strcmp(act, "vol_up") == 0) handleSerialCommand('+');
      else if (strcmp(act, "vol_down") == 0) handleSerialCommand('-');
    }
  }
}

void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len) {
  if (type == WS_EVT_DATA) {
    handleWebSocketMessage(arg, data, len);
  }
}

// ============================================================================
// MAIN SETUP & LOOP
// ============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\n========================================================");
  Serial.println("  🤖 ESP32-S3 VOICE ASSISTANT — STARTUP");
  Serial.println("========================================================");

  // Initialize BOOT button
  pinMode(BTN_BOOT, INPUT_PULLUP);

  // Check PSRAM Hardware Status
  if (psramFound()) {
    Serial.printf("[PSRAM] ✅ %u bytes (%.1f MB) Octal PSRAM initialized and active!\n",
                  ESP.getPsramSize(), (float)ESP.getPsramSize() / 1048576.0f);
  } else {
    Serial.println("[PSRAM] ⚠️ PSRAM not detected. Using internal DRAM.");
  }

  // Allocate speech buffer (in PSRAM or DRAM)
  speechBuffer = (int16_t*)ps_malloc(MAX_RECORD_SAMPLES * sizeof(int16_t));
  if (!speechBuffer) {
    speechBuffer = (int16_t*)malloc(MAX_RECORD_SAMPLES * sizeof(int16_t));
  }
  if (speechBuffer) {
    Serial.printf("[MEMORY] Allocated %u bytes speech buffer for Whisper STT (PSRAM: %s).\n",
                  (unsigned int)(MAX_RECORD_SAMPLES * sizeof(int16_t)),
                  psramFound() ? "YES" : "NO");
  } else {
    Serial.println("[MEMORY ERROR] Failed to allocate speech buffer!");
  }

  // Clear pre-roll buffer
  memset(preRollBuffer, 0, sizeof(preRollBuffer));
  preRollIndex = 0;

  // Create FreeRTOS Queues
  audioQueue = xQueueCreate(10, sizeof(AudioCommand));
  voiceQueue = xQueueCreate(4, sizeof(VoiceRecordMsg));

  // Initialize I2S Hardware Drivers
  initSpeakerI2S();
  initMicrophoneI2S();

  // Create Audio Output Task on Core 1 (Stack 8192)
  xTaskCreatePinnedToCore(audioTaskFunction, "AudioTask", 8192, NULL, 4, &audioTaskHandle, 1);

  // Create Voice & Intent Task on Core 1
  xTaskCreatePinnedToCore(voiceTaskFunction, "VoiceTask", 8192, NULL, 3, &voiceTaskHandle, 1);

  // Create Mic Sampling & VAD Task on Core 0
  xTaskCreatePinnedToCore(micTaskFunction, "MicTask", 6144, NULL, 5, &micTaskHandle, 0);

  // Play clean startup melody
  AudioCommand startCmd = { CMD_STARTUP };
  xQueueSend(audioQueue, &startCmd, 0);

  // Connect to Wi-Fi
  Serial.printf("[WIFI] Connecting to %s...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int wifiRetries = 0;
  while (WiFi.status() != WL_CONNECTED && wifiRetries < 25) {
    delay(400);
    Serial.print(".");
    wifiRetries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] Connected! IP Address: %s\n", WiFi.localIP().toString().c_str());
    udp.begin(WiFi.localIP(), 0);
  } else {
    Serial.println("\n[WIFI WARNING] Wi-Fi connection timed out. Offline features active.");
  }

  // Setup Web Dashboard
  ws.onEvent(onEvent);
  server.addHandler(&ws);
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/html", INDEX_HTML);
  });
  server.begin();
  Serial.printf("[WEB] Web Dashboard active at http://%s\n", WiFi.localIP().toString().c_str());

  printHelpMenu();
}

void loop() {
  // Check Serial commands
  if (Serial.available()) {
    char c = Serial.read();
    handleSerialCommand(c);
  }

  // Check physical BOOT button toggle (0ms Instant Wake Trigger)
  static bool lastBtnState = HIGH;
  bool btnState = digitalRead(BTN_BOOT);
  if (btnState == LOW && lastBtnState == HIGH) {
    delay(50); // Debounce
    if (digitalRead(BTN_BOOT) == LOW) {
      Serial.println("[BUTTON] BOOT button clicked! Simulating Wake Word ('Hey Burden')...");
      handleSerialCommand('w');
    }
  }
  lastBtnState = btnState;

  // Handle command window timeout
  if (assistantState == STATE_LISTENING_FOR_COMMAND && millis() > commandWindowExpiry) {
    Serial.println("[STATE] Command listening window timed out. Returning to IDLE wake word mode.");
    assistantState = STATE_IDLE_WAIT_WAKE;
    lastActionStatus = "Ready — Listening for 'Hey Burden'";
  }

  // Broadcast WebSocket Telemetry every 100ms
  static unsigned long lastWsBroadcast = 0;
  if (millis() - lastWsBroadcast > 100 && ws.count() > 0) {
    lastWsBroadcast = millis();
    JsonDocument doc;
    doc["rms"] = liveMicRMS;
    doc["peak"] = liveMicPeak;
    doc["transcript"] = lastTranscript;
    doc["status"] = lastActionStatus;
    doc["lights"] = lightsCurrentState;
    doc["vol"] = systemVolume;
    doc["gain"] = micGain;
    doc["state"] = (int)assistantState;
    String out;
    serializeJson(doc, out);
    ws.textAll(out);
  }

  vTaskDelay(pdMS_TO_TICKS(20));
}
