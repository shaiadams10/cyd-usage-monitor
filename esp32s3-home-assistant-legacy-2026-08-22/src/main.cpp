#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ESPAsyncWebServer.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <driver/i2s.h>
#include <math.h>
#include <ArduinoJson.h>
#include <Update.h>
#include <stdarg.h>
#include <esp_heap_caps.h>

#include "secrets.h"
#include "dashboard_gz.h"

// Mirror all firmware serial output into a bounded in-memory ring so the same
// diagnostics are available from the browser when USB serial is disconnected.
constexpr size_t DIAGNOSTIC_LINE_COUNT = 40;
constexpr size_t DIAGNOSTIC_LINE_LENGTH = 192;
char diagnosticLines[DIAGNOSTIC_LINE_COUNT][DIAGNOSTIC_LINE_LENGTH] = {};
char diagnosticPendingLine[DIAGNOSTIC_LINE_LENGTH] = {};
size_t diagnosticPendingLength = 0;
size_t diagnosticNextLine = 0;
size_t diagnosticStoredLines = 0;
volatile uint32_t diagnosticLogVersion = 0;
portMUX_TYPE diagnosticMux = portMUX_INITIALIZER_UNLOCKED;

void appendDiagnosticText(const char* text) {
  if (!text) return;
  portENTER_CRITICAL(&diagnosticMux);
  for (const char* p = text; *p; ++p) {
    if (*p == '\r') continue;
    if (*p == '\n') {
      diagnosticPendingLine[diagnosticPendingLength] = '\0';
      strlcpy(diagnosticLines[diagnosticNextLine], diagnosticPendingLine, DIAGNOSTIC_LINE_LENGTH);
      diagnosticNextLine = (diagnosticNextLine + 1) % DIAGNOSTIC_LINE_COUNT;
      if (diagnosticStoredLines < DIAGNOSTIC_LINE_COUNT) diagnosticStoredLines++;
      diagnosticLogVersion++;
      diagnosticPendingLength = 0;
      diagnosticPendingLine[0] = '\0';
    } else if (diagnosticPendingLength < DIAGNOSTIC_LINE_LENGTH - 1) {
      diagnosticPendingLine[diagnosticPendingLength++] = *p;
      diagnosticPendingLine[diagnosticPendingLength] = '\0';
    }
  }
  portEXIT_CRITICAL(&diagnosticMux);
}

String diagnosticLogSnapshot() {
  String output;
  output.reserve(DIAGNOSTIC_LINE_COUNT * 96);

  size_t stored;
  size_t next;
  portENTER_CRITICAL(&diagnosticMux);
  stored = diagnosticStoredLines;
  next = diagnosticNextLine;
  portEXIT_CRITICAL(&diagnosticMux);

  size_t first = (stored == DIAGNOSTIC_LINE_COUNT) ? next : 0;
  for (size_t i = 0; i < stored; ++i) {
    char line[DIAGNOSTIC_LINE_LENGTH];
    size_t index = (first + i) % DIAGNOSTIC_LINE_COUNT;
    portENTER_CRITICAL(&diagnosticMux);
    strlcpy(line, diagnosticLines[index], sizeof(line));
    portEXIT_CRITICAL(&diagnosticMux);
    output += line;
    output += '\n';
  }
  return output;
}

class DiagnosticSerialTee {
 public:
  explicit DiagnosticSerialTee(HardwareSerial& serial) : serial_(serial) {}

  void begin(unsigned long baud) { serial_.begin(baud); }

  template <typename T>
  void print(const T& value) {
    serial_.print(value);
    String rendered(value);
    appendDiagnosticText(rendered.c_str());
  }

  template <typename T>
  void println(const T& value) {
    serial_.println(value);
    String rendered(value);
    rendered += '\n';
    appendDiagnosticText(rendered.c_str());
  }

  void println() {
    serial_.println();
    appendDiagnosticText("\n");
  }

  int printf(const char* format, ...) {
    char buffer[320];
    va_list args;
    va_start(args, format);
    int required = vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    serial_.print(buffer);
    appendDiagnosticText(buffer);
    return required;
  }

 private:
  HardwareSerial& serial_;
};

DiagnosticSerialTee DebugSerial(Serial);

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1

// OLED I2C Pins
#define I2C_SDA 6
#define I2C_SCL 5

// MAX98357A I2S Speaker Pins (I2S_NUM_0 - TX)
#define I2S_SPEAKER_BCLK 17
#define I2S_SPEAKER_LRC  18
#define I2S_SPEAKER_DIN  8
#define I2S_PORT_SPEAKER I2S_NUM_0
#define SAMPLE_RATE 44100

// INMP441 I2S Microphone Pins (I2S_NUM_1 - RX)
#define I2S_MIC_SCK 15
#define I2S_MIC_WS  16
#define I2S_MIC_SD  7
#define I2S_PORT_MIC I2S_NUM_1
#define MIC_SAMPLE_RATE 16000

// Hardware BOOT Button Pin (GPIO 0)
#define BOOT_BUTTON_PIN 0

// Govee Local Hardware Lamp IPs & UDP Port (Fast Zero-Wait Control)
#define GOVEE_LAMP1_IP "192.0.2.20"
#define GOVEE_LAMP2_IP "192.0.2.21"
#define GOVEE_UDP_PORT 4003

// Target Home Assistant / Server defaults
#ifndef HA_SERVER_IP
#define HA_SERVER_IP "192.0.2.10"
#endif
#ifndef HA_SERVER_PORT
#define HA_SERVER_PORT 8123
#endif
#ifndef HA_API_TOKEN
#define HA_API_TOKEN ""
#endif
#ifndef HA_DEFAULT_LIGHT
#define HA_DEFAULT_LIGHT "all_lamps"
#endif
#ifndef HA_LAMP1_ENTITY
#define HA_LAMP1_ENTITY "light.lamp_one"
#endif
#ifndef HA_LAMP2_ENTITY
#define HA_LAMP2_ENTITY "light.lamp_two"
#endif

#define TTS_PORT "10201"
#define WHISPER_PORT 10300
#define WAKE_WORD_PORT 10400
#ifndef WAKE_WORD_MODEL
#define WAKE_WORD_MODEL "hey_burden"
#endif

// Fast Audio Buffers & Low-Latency Timing
#define MIC_FRAME_SAMPLES    256                        // 16ms frames @ 16kHz
#define WAKE_CHUNK_SAMPLES   1280                       // 80ms Wyoming frame; 5x fewer TCP headers
#define PREROLL_SAMPLES      4000                       // 250ms speech-onset protection
#define MAX_RECORD_SAMPLES   (MIC_SAMPLE_RATE * 45 / 10) // 4.5s command headroom
#define MIN_RECORD_SAMPLES   (MIC_SAMPLE_RATE * 6 / 10)  // 0.6s minimum capture
#define VAD_SILENCE_FRAMES   18                         // 288ms endpoint silence
#define VAD_START_FRAMES     2                          // 32ms rejects impulsive noise
#define WAKE_SETTLE_MS       110                        // speaker tail guard before listening
#define COMMAND_LISTEN_MS    5000                       // command must begin within 5s of earcon
#define DEFAULT_VOLUME       0.17f                      // master gain for tones, effects, and TTS

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

bool oledReady = false;
volatile float currentVolume = DEFAULT_VOLUME;
volatile bool stopRequested = false;
volatile bool speakBackEnabled = false;
String deviceIP = "Connecting...";

// Smart Home & Fixed Trigger Word State ("Hey Burden")
String haServerIP = String(HA_SERVER_IP);
int haServerPort = HA_SERVER_PORT;
String haApiToken = String(HA_API_TOKEN);
String haDefaultLight = String(HA_DEFAULT_LIGHT);
String triggerWord = "hey burden";
bool triggerWordEnabled = true;

enum AssistantState {
  STATE_IDLE_WAIT_WAKE,
  STATE_LISTENING_FOR_COMMAND
};

volatile AssistantState assistantState = STATE_IDLE_WAIT_WAKE;
volatile bool isSpeakerPlaying = false;
volatile bool manualRecordRequested = false;
volatile bool resetPreRollRequested = false;
volatile bool remoteWakeDetected = false;
volatile bool remoteWakeAvailable = false;
volatile bool wakeStreamConnected = false;
volatile bool voiceResetRequested = false;
volatile unsigned long listenNotBefore = 0;
unsigned long commandWindowExpiry = 0;
float micGain = 3.5f;       // 3.5x digital vocal pre-amplifier
float adaptiveNoiseFloor = 260.0f;
int vadThreshold = 750;     // Live adaptive start threshold, also shown in telemetry

enum SystemMode {
  MODE_MEDIA,
  MODE_SMART_HOME
};

volatile SystemMode currentMode = MODE_SMART_HOME;
String lastOledMessage = "Voice Satellite Ready";
String lastOledTitle = "VOICE SATELLITE";
String lastSpeechHeard = "";
String currentActionText = "Ready";

enum AudioType {
  CMD_NONE,
  CMD_WAKE_EARCON,
  CMD_CHIME,
  CMD_COIN,
  CMD_FANFARE,
  CMD_SWEEP,
  CMD_SPEAK_VOICE,
  CMD_STOP
};

struct AudioCommand {
  AudioType type;
  char text[192];
};

struct VoiceRecordMsg {
  int16_t* pcmData;
  size_t sampleCount;
};

struct HaSyncCommand {
  char action[16];
  char entityId[72];
};

struct WakeAudioFrame {
  int16_t samples[MIC_FRAME_SAMPLES];
  uint16_t sampleCount;
};

struct SmartHomeResult {
  bool handled;
  bool success;
  String action;
  String target;
  String message;
};

// FreeRTOS Task and Queue Handles
TaskHandle_t audioTaskHandle = NULL;
TaskHandle_t voiceTaskHandle = NULL;
TaskHandle_t micTaskHandle = NULL;
TaskHandle_t haSyncTaskHandle = NULL;
TaskHandle_t wakeTaskHandle = NULL;
QueueHandle_t audioQueue = NULL;
QueueHandle_t voiceQueue = NULL;
QueueHandle_t haSyncQueue = NULL;
QueueHandle_t wakeAudioQueue = NULL;
SemaphoreHandle_t oledMutex = NULL;

// Global Audio and VAD Buffers
int16_t* recordBuffer = NULL;
int16_t preRollBuffer[PREROLL_SAMPLES];
int16_t wakeNetworkChunk[WAKE_CHUNK_SAMPLES];
size_t preRollIndex = 0;
volatile int recordSampleCount = 0;
volatile bool isRecordingVoice = false;
volatile bool isTranscribing = false;

// Forward declarations
void broadcastStatus(const char* state, const char* detail);
const char* voicePhaseName();
unsigned long commandWindowRemainingMs();
void resetVoicePipeline(const char* reason);
void updateOledUI(const char* titleBanner, const char* speechText, const char* actionText, bool isInterim = false);
void renderDisplay(const char* title, const char* line1, const char* line2);
void renderCustomMessage(const char* title, const char* message);
void renderSpeechDisplay(const char* text, bool isInterim, const char* statusMsg);
void renderSmartHomeDisplay(const char* actionTitle, const char* target, const char* statusMsg);
bool sendDirectGoveeUdp(const char* ip, int val);
bool sendHomeAssistantLightCommand(const char* action, const char* entityId);
bool sendHomeAssistantRestCommand(const char* action, const char* entityId);
bool wakeServiceHasModel(const char* modelName);
void beginConfirmedWake(const char* source);
bool containsWakeWord(const String& clean);
String stripWakeWord(const String& clean);
SmartHomeResult parseAndExecuteVoiceCommand(const String& rawText);

// ---------------------------------------------------------------------------
// Govee Local UDP Fast Controller (<5ms Latency Unicast)
// ---------------------------------------------------------------------------

bool sendDirectGoveeUdp(const char* ip, int val) {
  WiFiUDP udp;
  if (udp.beginPacket(ip, GOVEE_UDP_PORT)) {
    char buf[80];
    snprintf(buf, sizeof(buf), "{\"msg\":{\"cmd\":\"turn\",\"data\":{\"value\":%d}}}", val);
    udp.write((const uint8_t*)buf, strlen(buf));
    bool sent = (udp.endPacket() == 1);
    DebugSerial.printf("[UDP GOVEE] Sent direct UDP turn %d to %s:%d\n", val, ip, GOVEE_UDP_PORT);
    return sent;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Home Assistant REST API Client & Govee Sync
// ---------------------------------------------------------------------------

bool sendHomeAssistantRestCommand(const char* action, const char* entityId) {
  if (WiFi.status() != WL_CONNECTED) {
    DebugSerial.println("[HA REST] Wi-Fi not connected");
    return false;
  }

  HTTPClient http;
  String url = "http://" + haServerIP + ":" + String(haServerPort) + "/api/services/light/" + String(action);
  DebugSerial.printf("[HA REST] Calling %s for entity '%s'...\n", url.c_str(), entityId);

  http.begin(url);
  http.setTimeout(3500);
  http.addHeader("Content-Type", "application/json");
  if (haApiToken.length() > 0) {
    http.addHeader("Authorization", "Bearer " + haApiToken);
  }

  String payload;
  if (String(entityId) == "all") {
    payload = "{\"entity_id\": \"all\"}";
  } else if (String(entityId) == "all_lamps" || String(entityId) == "lamps") {
    payload = "{\"entity_id\": [\"" + String(HA_LAMP1_ENTITY) + "\", \"" + String(HA_LAMP2_ENTITY) + "\"]}";
  } else if (String(entityId) == "lamp1") {
    payload = "{\"entity_id\": \"" + String(HA_LAMP1_ENTITY) + "\"}";
  } else if (String(entityId) == "lamp2") {
    payload = "{\"entity_id\": \"" + String(HA_LAMP2_ENTITY) + "\"}";
  } else {
    payload = "{\"entity_id\": \"" + String(entityId) + "\"}";
  }

  int code = http.POST(payload);
  DebugSerial.printf("[HA REST] Response code: %d\n", code);
  bool success = (code >= 200 && code < 300);
  http.end();
  return success;
}

bool sendHomeAssistantLightCommand(const char* action, const char* entityId) {
  if (WiFi.status() != WL_CONNECTED) {
    DebugSerial.println("[LIGHT] Wi-Fi not connected");
    return false;
  }

  // Apply supported Govee actions immediately; HA state sync runs separately.
  static int goveeLampState = 0;
  int turnVal = -1;
  if (strcmp(action, "turn_on") == 0) {
    turnVal = 1;
    goveeLampState = 1;
  } else if (strcmp(action, "turn_off") == 0) {
    turnVal = 0;
    goveeLampState = 0;
  } else if (strcmp(action, "toggle") == 0) {
    goveeLampState = (goveeLampState == 1) ? 0 : 1;
    turnVal = goveeLampState;
  }

  bool directHandled = false;
  if (turnVal >= 0) {
    if (strcmp(entityId, HA_LAMP1_ENTITY) == 0 || strcmp(entityId, "lamp1") == 0) {
      directHandled = sendDirectGoveeUdp(GOVEE_LAMP1_IP, turnVal);
    } else if (strcmp(entityId, HA_LAMP2_ENTITY) == 0 || strcmp(entityId, "lamp2") == 0) {
      directHandled = sendDirectGoveeUdp(GOVEE_LAMP2_IP, turnVal);
    } else if (strcmp(entityId, "all_lamps") == 0 || strcmp(entityId, "all") == 0 || strcmp(entityId, "lamps") == 0) {
      bool first = sendDirectGoveeUdp(GOVEE_LAMP1_IP, turnVal);
      bool second = sendDirectGoveeUdp(GOVEE_LAMP2_IP, turnVal);
      directHandled = first || second;
    }
  }

  HaSyncCommand sync = {};
  snprintf(sync.action, sizeof(sync.action), "%s", action);
  snprintf(sync.entityId, sizeof(sync.entityId), "%s", entityId);
  bool queued = haSyncQueue && (xQueueSend(haSyncQueue, &sync, 0) == pdTRUE);
  if (!queued) {
    DebugSerial.println("[HA SYNC] Queue full; direct action was not delayed");
  }
  return directHandled || queued;
}

void haSyncTaskFunction(void* param) {
  HaSyncCommand cmd;
  for (;;) {
    if (xQueueReceive(haSyncQueue, &cmd, portMAX_DELAY) == pdTRUE) {
      bool ok = sendHomeAssistantRestCommand(cmd.action, cmd.entityId);
      broadcastStatus(ok ? "smart_home" : "error", ok ? "Home Assistant state synchronized" : "Home Assistant sync failed; direct action may still have succeeded");
    }
  }
}

// ---------------------------------------------------------------------------
// ACCENT TOLERANCE & PHONETIC WAKE WORD MATCHING ("Hey Burden")
// ---------------------------------------------------------------------------

bool containsWakeWord(const String& clean) {
  if (!triggerWordEnabled) return false;
  const char* prefixes[] = {
    "hey burden", "hey birden", "hey birdin", "hey borden", "hey berden",
    "hi burden", "okay burden", "ok burden"
  };
  for (const char* prefix : prefixes) {
    size_t length = strlen(prefix);
    if (clean.startsWith(prefix) && (clean.length() == length || clean[length] == ' ')) return true;
  }
  return false;
}

String stripWakeWord(const String& clean) {
  String s = clean;
  const char* prefixes[] = {
    "hey burden", "hey birden", "hey birdin", "hey borden", "hey berden",
    "hi burden", "okay burden", "ok burden"
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

void beginConfirmedWake(const char* source) {
  assistantState = STATE_LISTENING_FOR_COMMAND;
  commandWindowExpiry = 0;  // Starts after the earcon, not while it is playing.
  listenNotBefore = millis() + 1000;  // Provisional guard until AudioTask timestamps the earcon tail.
  resetPreRollRequested = true;
  updateOledUI("WAKE DETECTED", "Hey Burden", "Act: Preparing Microphone");
  broadcastStatus("wake_detected", source);

  AudioCommand audioCmd = { CMD_WAKE_EARCON, "" };
  if (!audioQueue || xQueueSend(audioQueue, &audioCmd, 0) != pdTRUE) {
    listenNotBefore = millis() + WAKE_SETTLE_MS;
    commandWindowExpiry = listenNotBefore + COMMAND_LISTEN_MS;
  }
}

// ---------------------------------------------------------------------------
// Smart Home Intent & Multi-Stage Voice Command Parser
// ---------------------------------------------------------------------------

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

  // Clean punctuation
  String clean = "";
  for (unsigned int i = 0; i < text.length(); i++) {
    char c = text[i];
    if (isalnum(c) || c == ' ') clean += c;
  }
  clean.trim();

  if (clean.length() == 0) return res;

  DebugSerial.printf("[INTENT] Analyzing (State=%s): \"%s\"\n",
                (assistantState == STATE_LISTENING_FOR_COMMAND) ? "COMMAND_WAIT" : "IDLE_WAKE",
                clean.c_str());

  // 1. If currently IDLE (Waiting for Wake Word or Direct Command)
  if (assistantState == STATE_IDLE_WAIT_WAKE) {
    if (containsWakeWord(clean)) {
      String cmd = stripWakeWord(clean);

      // If user ONLY spoke the wake word ("Hey Burden", "Hey Birdie", "Hey Britain", etc.)
      if (cmd.length() == 0) {
        res.handled = true;
        res.success = true;
        res.action = "WAKE_WORD";
        res.target = "Hey Burden";
        res.message = "Trigger recognized! Listening for command...";

        beginConfirmedWake("Wake phrase confirmed by Whisper fallback");
        return res;
      }

      // If user spoke Wake Word + Command in one continuous breath ("Hey Burden turn on lamp 1")
      clean = cmd;
    } else {
      // Check if user directly gave a light command without wake word
      bool directOn = (clean.indexOf("turn on") >= 0 || clean.indexOf("switch on") >= 0 ||
                       clean.indexOf("lights on") >= 0 || clean.indexOf("light on") >= 0 ||
                       clean.indexOf("lamps on") >= 0 || clean.indexOf("lamp on") >= 0 ||
                       clean.indexOf("likes on") >= 0 || clean.indexOf("light zone") >= 0);
      bool directOff = (clean.indexOf("turn off") >= 0 || clean.indexOf("switch off") >= 0 ||
                         clean.indexOf("lights off") >= 0 || clean.indexOf("light off") >= 0 ||
                         clean.indexOf("lamps off") >= 0 || clean.indexOf("lamp off") >= 0 ||
                         clean.indexOf("likes off") >= 0 || clean.indexOf("nights off") >= 0);
      bool directToggle = (clean.indexOf("toggle") >= 0 || clean.indexOf("flip") >= 0);
      if (!directOn && !directOff && !directToggle) {
        return res;
      }
    }
  }

  // 2. Command Parsing (When in Command State OR One-Shot Wake+Command OR Direct Command)
  String cmd = clean;

  bool isTurnOn = (cmd.indexOf("turn on") >= 0 || cmd.indexOf("switch on") >= 0 ||
                   cmd.indexOf("lights on") >= 0 || cmd.indexOf("light on") >= 0 ||
                   cmd.indexOf("likes on") >= 0 || cmd.indexOf("like on") >= 0 ||
                   cmd.indexOf("light zone") >= 0 || cmd.indexOf("lights in") >= 0 ||
                   cmd.indexOf("night on") >= 0 || cmd.indexOf("nights on") >= 0 ||
                   cmd.indexOf("lamps on") >= 0 || cmd.indexOf("lamp on") >= 0 ||
                   cmd == "on" || cmd.startsWith("on ") || cmd.endsWith(" on"));
  bool isTurnOff = (cmd.indexOf("turn off") >= 0 || cmd.indexOf("switch off") >= 0 ||
                    cmd.indexOf("lights off") >= 0 || cmd.indexOf("light off") >= 0 ||
                    cmd.indexOf("likes off") >= 0 || cmd.indexOf("like off") >= 0 ||
                    cmd.indexOf("nights off") >= 0 || cmd.indexOf("night off") >= 0 ||
                    cmd.indexOf("lamps off") >= 0 || cmd.indexOf("lamp off") >= 0 ||
                    cmd == "off" || cmd.startsWith("off ") || cmd.endsWith(" off"));
  bool isToggle = (cmd.indexOf("toggle") >= 0 || cmd.indexOf("flip") >= 0);

  if (isTurnOn || isTurnOff || isToggle) {
    res.handled = true;
    String entity = "all_lamps";
    String targetDisplayName = "All Lamps";

    if (cmd.indexOf("lamp 1") >= 0 || cmd.indexOf("lamp one") >= 0 || cmd.indexOf("first") >= 0) {
      entity = HA_LAMP1_ENTITY;
      targetDisplayName = "Lamp 1";
    } else if (cmd.indexOf("lamp 2") >= 0 || cmd.indexOf("lamp two") >= 0 || cmd.indexOf("second") >= 0) {
      entity = HA_LAMP2_ENTITY;
      targetDisplayName = "Lamp 2";
    } else if (cmd.indexOf("living room") >= 0) {
      entity = "light.living_room_lights";
      targetDisplayName = "Living Room";
    } else if (cmd.indexOf("bedroom") >= 0) {
      entity = "light.bedroom_lights";
      targetDisplayName = "Bedroom";
    }

    String action = isTurnOn ? "turn_on" : (isTurnOff ? "turn_off" : "toggle");
    res.action = action;
    res.target = entity;

    bool ok = sendHomeAssistantLightCommand(action.c_str(), entity.c_str());
    res.success = ok;

    String actionName = (action == "turn_on") ? "Turned ON " : ((action == "turn_off") ? "Turned OFF " : "Toggled ");
    res.message = actionName + targetDisplayName;

    // Instant speaker feedback
    AudioCommand audioCmd;
    audioCmd.type = (action == "turn_on" || action == "toggle") ? CMD_COIN : CMD_CHIME;
    audioCmd.text[0] = '\0';
    xQueueSend(audioQueue, &audioCmd, 0);

    // Reset state machine back to Idle
    assistantState = STATE_IDLE_WAIT_WAKE;
    return res;
  }

  // Sound and Media Intents
  if (cmd.indexOf("chime") >= 0) {
    AudioCommand audioCmd = { CMD_CHIME, "" };
    xQueueSend(audioQueue, &audioCmd, 0);
    res.handled = true; res.success = true; res.action = "SOUND_CHIME"; res.target = "Chime"; res.message = "Playing chime";
    assistantState = STATE_IDLE_WAIT_WAKE;
    return res;
  }
  if (cmd.indexOf("fanfare") >= 0 || cmd.indexOf("party") >= 0) {
    AudioCommand audioCmd = { CMD_FANFARE, "" };
    xQueueSend(audioQueue, &audioCmd, 0);
    res.handled = true; res.success = true; res.action = "SOUND_FANFARE"; res.target = "Fanfare"; res.message = "Playing fanfare";
    assistantState = STATE_IDLE_WAIT_WAKE;
    return res;
  }
  if (cmd.indexOf("coin") >= 0 || cmd.indexOf("mario") >= 0) {
    AudioCommand audioCmd = { CMD_COIN, "" };
    xQueueSend(audioQueue, &audioCmd, 0);
    res.handled = true; res.success = true; res.action = "SOUND_COIN"; res.target = "Coin"; res.message = "Playing coin";
    assistantState = STATE_IDLE_WAIT_WAKE;
    return res;
  }
  if (cmd.indexOf("stop") >= 0) {
    AudioCommand audioCmd = { CMD_STOP, "" };
    xQueueSend(audioQueue, &audioCmd, 0);
    res.handled = true; res.success = true; res.action = "AUDIO_STOP"; res.target = "Audio"; res.message = "Stopped audio";
    assistantState = STATE_IDLE_WAIT_WAKE;
    return res;
  }

  if (assistantState == STATE_LISTENING_FOR_COMMAND) {
    assistantState = STATE_IDLE_WAIT_WAKE;
  }

  return res;
}

// ---------------------------------------------------------------------------
// Wyoming Whisper STT Client (Streams recorded audio directly to Whisper)
// ---------------------------------------------------------------------------

bool sendAudioToWhisper(int16_t* pcmData, size_t numSamples, String& outTranscript) {
  if (numSamples < 4000 || !pcmData || voiceResetRequested) return false;

  DebugSerial.printf("[WHISPER] Connecting to %s:%d (%u samples, %.2fs)...\n",
                haServerIP.c_str(), WHISPER_PORT, (unsigned int)numSamples, (float)numSamples / MIC_SAMPLE_RATE);

  WiFiClient client;
  client.setTimeout(6000);
  if (!client.connect(haServerIP.c_str(), WHISPER_PORT)) {
    DebugSerial.println("[WHISPER ERROR] Could not connect to Whisper STT server");
    return false;
  }
  client.setNoDelay(true);

  // 1. Transcribe event with domain context prompt bias
  client.print("{\"type\":\"transcribe\",\"data\":{\"language\":\"en\",\"prompt\":\"Hey Burden, Alexa, Hey Jarvis, Okay Nabu, lights on, lights off, turn on, turn off, lamp on, lamp off, toggle.\"}}\n");

  // 2. Audio start event
  client.print("{\"type\":\"audio-start\",\"data\":{\"rate\":16000,\"width\":2,\"channels\":1}}\n");

  // 3. Stream in atomic Wyoming audio chunks of 1024 samples (2048 bytes)
  const size_t CHUNK_SAMPLES = 1024;
  size_t offset = 0;
  while (offset < numSamples && client.connected() && !voiceResetRequested) {
    size_t count = (numSamples - offset > CHUNK_SAMPLES) ? CHUNK_SAMPLES : (numSamples - offset);
    size_t bytes = count * sizeof(int16_t);
    client.printf("{\"type\":\"audio-chunk\",\"data\":{\"rate\":16000,\"width\":2,\"channels\":1},\"payload_length\":%u}\n", (unsigned int)bytes);
    client.write((const uint8_t*)(pcmData + offset), bytes);
    offset += count;
  }

  // 4. Audio stop event
  if (voiceResetRequested) {
    client.stop();
    DebugSerial.println("[WHISPER] Cancelled by voice-pipeline reset");
    return false;
  }

  client.print("{\"type\":\"audio-stop\",\"data\":{}}\n");
  client.flush();

  DebugSerial.println("[WHISPER] Audio stream sent. Waiting for response...");

  // 5. Read response with timeout
  unsigned long startWait = millis();
  while (client.connected() && millis() - startWait < 8000 && !voiceResetRequested) {
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
                DebugSerial.printf("[WHISPER SUCCESS] Transcribed: \"%s\"\n", outTranscript.c_str());
                return (outTranscript.length() > 0);
              }
            }
          }
          
          if (doc["text"].is<const char*>()) {
            outTranscript = String((const char*)doc["text"]);
            outTranscript.trim();
            client.stop();
            DebugSerial.printf("[WHISPER SUCCESS] Transcribed: \"%s\"\n", outTranscript.c_str());
            return (outTranscript.length() > 0);
          } else if (doc["data"]["text"].is<const char*>()) {
            outTranscript = String((const char*)doc["data"]["text"]);
            outTranscript.trim();
            client.stop();
            DebugSerial.printf("[WHISPER SUCCESS] Transcribed: \"%s\"\n", outTranscript.c_str());
            return (outTranscript.length() > 0);
          }
        }
      }
    }
    delay(5);
  }
  client.stop();
  if (voiceResetRequested) {
    DebugSerial.println("[WHISPER] Cancelled by voice-pipeline reset");
    return false;
  }
  DebugSerial.println("[WHISPER TIMEOUT] No transcript returned");
  return false;
}

// ---------------------------------------------------------------------------
// Streaming Wyoming openWakeWord Client — dedicated wake inference, no STT
// ---------------------------------------------------------------------------

bool wakeServiceHasModel(const char* modelName) {
  if (WiFi.status() != WL_CONNECTED) return false;

  WiFiClient client;
  client.setTimeout(1200);
  if (!client.connect(haServerIP.c_str(), WAKE_WORD_PORT)) return false;
  client.setNoDelay(true);
  client.print("{\"type\":\"describe\",\"data\":{}}\n");

  String header = client.readStringUntil('\n');
  header.trim();
  JsonDocument headerDoc;
  if (deserializeJson(headerDoc, header)) {
    client.stop();
    return false;
  }

  int dataLength = headerDoc["data_length"] | 0;
  if (dataLength <= 0 || dataLength > 4096) {
    client.stop();
    return false;
  }

  char payload[4097];
  size_t bytesRead = client.readBytes(payload, dataLength);
  payload[bytesRead] = '\0';
  client.stop();

  JsonDocument info;
  if (deserializeJson(info, payload)) return false;
  JsonArray programs = info["wake"].as<JsonArray>();
  for (JsonObject program : programs) {
    for (JsonObject model : program["models"].as<JsonArray>()) {
      const char* name = model["name"] | "";
      if (strcmp(name, modelName) == 0) return true;
    }
  }
  return false;
}

void stopWakeStream(WiFiClient& client) {
  if (client.connected()) {
    client.print("{\"type\":\"audio-stop\",\"data\":{}}\n");
    client.flush();
  }
  client.stop();
  wakeStreamConnected = false;
}

bool writeWakePayload(WiFiClient& client, const uint8_t* data, size_t length) {
  size_t sent = 0;
  const unsigned long deadline = millis() + 600;

  // Keep Wyoming payload writes bounded and yield so a temporary lwIP buffer
  // shortage does not corrupt the frame or start a reconnect storm that
  // starves the dashboard.
  while (sent < length && client.connected() && (long)(millis() - deadline) < 0) {
    size_t piece = min((size_t)512, length - sent);
    size_t written = client.write(data + sent, piece);
    if (written > 0) sent += written;
    vTaskDelay(pdMS_TO_TICKS(1));
  }
  return sent == length;
}

void wakeTaskFunction(void* param) {
  WiFiClient client;
  bool streamStarted = false;
  unsigned long nextModelProbe = 0;
  unsigned long nextConnectAttempt = 0;
  WakeAudioFrame frame;
  size_t wakeChunkSamples = 0;

  for (;;) {
    if (!remoteWakeAvailable && WiFi.status() == WL_CONNECTED && millis() >= nextModelProbe) {
      remoteWakeAvailable = wakeServiceHasModel(WAKE_WORD_MODEL);
      nextModelProbe = millis() + 30000;
      DebugSerial.printf("[WAKE] Model '%s' %s on openWakeWord :%d\n", WAKE_WORD_MODEL,
                    remoteWakeAvailable ? "available" : "not installed; using Whisper fallback",
                    WAKE_WORD_PORT);
    }

    bool shouldStream = remoteWakeAvailable && triggerWordEnabled &&
                        assistantState == STATE_IDLE_WAIT_WAKE && !isSpeakerPlaying &&
                        !isRecordingVoice && !isTranscribing && WiFi.status() == WL_CONNECTED;
    if (!shouldStream) {
      if (streamStarted) stopWakeStream(client);
      streamStarted = false;
      wakeChunkSamples = 0;
      while (wakeAudioQueue && xQueueReceive(wakeAudioQueue, &frame, 0) == pdTRUE) {}
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }

    if (!streamStarted) {
      if ((long)(millis() - nextConnectAttempt) < 0) {
        vTaskDelay(pdMS_TO_TICKS(20));
        continue;
      }
      client.setTimeout(500);
      if (!client.connect(haServerIP.c_str(), WAKE_WORD_PORT)) {
        client.stop();
        remoteWakeAvailable = false;
        nextModelProbe = millis() + 5000;
        nextConnectAttempt = millis() + 500;
        vTaskDelay(pdMS_TO_TICKS(100));
        continue;
      }
      // Let TCP coalesce each small JSON header and PCM frame. Disabling
      // Nagle here exhausts the ESP32's lwIP packet buffers and makes the
      // HTTP/WebSocket dashboard appear offline during continuous listening.
      client.setNoDelay(false);
      client.printf("{\"type\":\"detect\",\"data\":{\"names\":[\"%s\"]}}\n", WAKE_WORD_MODEL);
      client.print("{\"type\":\"audio-start\",\"data\":{\"rate\":16000,\"width\":2,\"channels\":1}}\n");
      streamStarted = true;
      wakeStreamConnected = true;
      wakeChunkSamples = 0;
      DebugSerial.printf("[WAKE] Streaming 16kHz audio to model '%s'\n", WAKE_WORD_MODEL);
    }

    if (xQueueReceive(wakeAudioQueue, &frame, pdMS_TO_TICKS(25)) == pdTRUE) {
      size_t offset = 0;
      while (offset < frame.sampleCount) {
        size_t copyCount = min((size_t)frame.sampleCount - offset,
                               (size_t)WAKE_CHUNK_SAMPLES - wakeChunkSamples);
        memcpy(wakeNetworkChunk + wakeChunkSamples, frame.samples + offset, copyCount * sizeof(int16_t));
        wakeChunkSamples += copyCount;
        offset += copyCount;

        if (wakeChunkSamples == WAKE_CHUNK_SAMPLES) {
          const size_t bytes = WAKE_CHUNK_SAMPLES * sizeof(int16_t);
          client.printf("{\"type\":\"audio-chunk\",\"data\":{\"rate\":16000,\"width\":2,\"channels\":1},\"payload_length\":%u}\n",
                        (unsigned int)bytes);
          if (!writeWakePayload(client, (const uint8_t*)wakeNetworkChunk, bytes)) {
            client.stop();
            streamStarted = false;
            wakeStreamConnected = false;
            wakeChunkSamples = 0;
            nextConnectAttempt = millis() + 250;
            break;
          }
          wakeChunkSamples = 0;
        }
      }
    }

    while (client.available()) {
      String line = client.readStringUntil('\n');
      line.trim();
      if (line.length() == 0) continue;
      JsonDocument event;
      if (deserializeJson(event, line)) continue;

      int dataLength = event["data_length"] | 0;
      if (dataLength > 0 && dataLength < 2048) {
        uint8_t discard[256];
        int remaining = dataLength;
        while (remaining > 0) {
          size_t count = client.readBytes(discard, min(remaining, (int)sizeof(discard)));
          if (count == 0) break;
          remaining -= count;
        }
      }

      const char* type = event["type"] | "";
      if (strcmp(type, "detection") == 0) {
        DebugSerial.printf("[WAKE] openWakeWord detected '%s'\n", WAKE_WORD_MODEL);
        remoteWakeDetected = true;
        stopWakeStream(client);
        streamStarted = false;
        wakeChunkSamples = 0;
        break;
      }
    }

    if (streamStarted && !client.connected()) {
      client.stop();
      streamStarted = false;
      wakeStreamConnected = false;
      wakeChunkSamples = 0;
      nextConnectAttempt = millis() + 250;
    }

  }
}

// ---------------------------------------------------------------------------
// Decoupled Asynchronous Voice & Intent Processing Task — Core 1
// ---------------------------------------------------------------------------

void voiceTaskFunction(void* param) {
  VoiceRecordMsg msg;
  for (;;) {
    if (xQueueReceive(voiceQueue, &msg, portMAX_DELAY) == pdTRUE) {
      String transcript = "";

      if (msg.pcmData && msg.sampleCount > 0) {
        updateOledUI("TRANSCRIBING", "...", "Act: Whisper STT (10300)", true);
        broadcastStatus("transcribing", "Transcribing speech...");

        sendAudioToWhisper(msg.pcmData, msg.sampleCount, transcript);
        isTranscribing = false;
        if (voiceResetRequested) {
          voiceResetRequested = false;
          transcript = "";
          broadcastStatus("idle", "Voice pipeline reset — ready for 'Hey Burden'");
        }
      }

      if (transcript.length() > 0) {
        DebugSerial.printf("[VOICE HUB] Heard: \"%s\"\n", transcript.c_str());
        lastSpeechHeard = transcript;
        broadcastStatus("idle", ("Heard: " + transcript).c_str());

        // Parse Smart Home intents and trigger words
        SmartHomeResult res = parseAndExecuteVoiceCommand(transcript);
        if (res.handled) {
          DebugSerial.printf("[SMART HOME] Action: %s | Target: %s (%s)\n", res.action.c_str(), res.target.c_str(), res.success ? "OK" : "ERR");

          if (res.action == "turn_on") {
            renderSmartHomeDisplay("LIGHTS ON", res.target.c_str(), "Turning on...");
          } else if (res.action == "turn_off") {
            renderSmartHomeDisplay("LIGHTS OFF", res.target.c_str(), "Turning off...");
          } else if (res.action == "toggle") {
            renderSmartHomeDisplay("TOGGLE LIGHT", res.target.c_str(), "Toggling...");
          } else if (res.action == "WAKE_WORD") {
            updateOledUI("WAKE DETECTED", transcript.c_str(), "Act: Wake Word Detected");
          } else {
            updateOledUI("VOICE COMMAND", transcript.c_str(), ("Act: " + res.message).c_str());
          }

          // Broadcast to Web Dashboard
          JsonDocument doc;
          doc["type"] = "smart_home_action";
          doc["action"] = res.action;
          doc["target"] = res.target;
          doc["success"] = res.success;
          doc["message"] = res.message;
          doc["transcript"] = transcript;
          String out;
          serializeJson(doc, out);
          ws.textAll(out);

          if (speakBackEnabled && res.action != "WAKE_WORD" && res.action.indexOf("SOUND_") < 0 && res.action != "AUDIO_STOP") {
            AudioCommand cmd;
            cmd.type = CMD_SPEAK_VOICE;
            snprintf(cmd.text, sizeof(cmd.text), "%s", res.message.c_str());
            xQueueSend(audioQueue, &cmd, 0);
          }
        } else {
          updateOledUI("VOICE COMMAND", transcript.c_str(), "Act: Voice Recognized");
          if (speakBackEnabled) {
            AudioCommand cmd;
            cmd.type = CMD_SPEAK_VOICE;
            snprintf(cmd.text, sizeof(cmd.text), "I heard: %s", transcript.c_str());
            xQueueSend(audioQueue, &cmd, 0);
          }
        }
      } else {
        if (assistantState == STATE_LISTENING_FOR_COMMAND) {
          updateOledUI("WAKE DETECTED", "Hey Burden", "Act: Listening for Command");
        } else {
          updateOledUI("VOICE SATELLITE", lastSpeechHeard.c_str(), "Act: Listening (16kHz)");
        }
        broadcastStatus("idle", "No speech recognized");
      }
    }
  }
}

// ---------------------------------------------------------------------------
// FreeRTOS INMP441 Mic Sampling & Stream Task — Core 0
// ---------------------------------------------------------------------------

void micTaskFunction(void* param) {
  const size_t DMA_READ_SAMPLES = MIC_FRAME_SAMPLES;
  int32_t rawBuffer[DMA_READ_SAMPLES];
  int16_t pcmChunk[DMA_READ_SAMPLES];

  // 75Hz IIR High-Pass Filter State (removes DC bias and room rumble)
  float x_prev = 0.0f;
  float y_prev = 0.0f;
  const float alpha = 0.9714f;

  int silenceCount = 0;
  int speechStartCount = 0;
  size_t currentSampleCount = 0;

  for (;;) {
    size_t bytesRead = 0;
    esp_err_t err = i2s_read(I2S_PORT_MIC, rawBuffer, sizeof(rawBuffer), &bytesRead, pdMS_TO_TICKS(50));
    if (err != ESP_OK || bytesRead == 0) {
      vTaskDelay(pdMS_TO_TICKS(5));
      continue;
    }

    size_t samplesRead = bytesRead / sizeof(int32_t);
    double sumSquares = 0.0;

    if (resetPreRollRequested) {
      resetPreRollRequested = false;
      memset(preRollBuffer, 0, sizeof(preRollBuffer));
      preRollIndex = 0;
    }

    for (size_t i = 0; i < samplesRead; i++) {
      // INMP441 is 24-bit MSB-aligned in 32-bit slot
      int32_t val32 = rawBuffer[i] >> 8;
      float sampleFloat = ((float)val32 / 256.0f) * micGain; // 3.5x vocal pre-amp

      // 75Hz High-Pass Filter
      float filtered = alpha * (y_prev + sampleFloat - x_prev);
      x_prev = sampleFloat;
      y_prev = filtered;

      // Soft AGC headroom compression (prevents clipping when speaking loud or close)
      if (filtered > 24000.0f) filtered = 24000.0f + (filtered - 24000.0f) * 0.30f;
      else if (filtered < -24000.0f) filtered = -24000.0f + (filtered + 24000.0f) * 0.30f;

      if (filtered > 32767.0f) filtered = 32767.0f;
      if (filtered < -32768.0f) filtered = -32768.0f;

      int16_t sample16 = (int16_t)filtered;
      pcmChunk[i] = sample16;

      // Circular pre-roll buffer protects the first syllable after VAD onset.
      preRollBuffer[preRollIndex] = sample16;
      preRollIndex = (preRollIndex + 1) % PREROLL_SAMPLES;

      sumSquares += (double)sample16 * (double)sample16;
    }

    float rms = sqrtf((float)(sumSquares / samplesRead));

    // Keep wake inference off the I2S task: enqueue fixed 16ms frames to its
    // dedicated network worker and drop a frame rather than ever block audio.
    if (remoteWakeAvailable && triggerWordEnabled && assistantState == STATE_IDLE_WAIT_WAKE &&
        !isSpeakerPlaying && !isRecordingVoice && !isTranscribing && wakeAudioQueue) {
      WakeAudioFrame wakeFrame = {};
      wakeFrame.sampleCount = min(samplesRead, (size_t)MIC_FRAME_SAMPLES);
      memcpy(wakeFrame.samples, pcmChunk, wakeFrame.sampleCount * sizeof(int16_t));
      xQueueSend(wakeAudioQueue, &wakeFrame, 0);
    }

    // Adaptive noise floor with hysteresis. Ignore obvious speech spikes so a
    // loud utterance cannot desensitize the next command.
    if (!isRecordingVoice && !isSpeakerPlaying && rms < max(1200.0f, adaptiveNoiseFloor * 3.0f)) {
      adaptiveNoiseFloor = adaptiveNoiseFloor * 0.985f + rms * 0.015f;
    }
    float startThreshold = max(520.0f, adaptiveNoiseFloor * 2.8f);
    float stopThreshold = max(380.0f, adaptiveNoiseFloor * 1.55f);
    vadThreshold = (int)startThreshold;

    // Manual capture remains available for dashboard/push-to-talk requests,
    // but can never arm while the speaker or its acoustic tail is active.
    if (manualRecordRequested && !isRecordingVoice && !isTranscribing && !isSpeakerPlaying &&
        millis() >= listenNotBefore) {
      manualRecordRequested = false;
      isRecordingVoice = true;
      currentSampleCount = 0;
      silenceCount = 0;

      // Copy pre-roll buffer so the opening syllable is intact.
      if (recordBuffer) {
        for (size_t k = 0; k < PREROLL_SAMPLES; k++) {
          size_t srcIdx = (preRollIndex + k) % PREROLL_SAMPLES;
          recordBuffer[currentSampleCount++] = preRollBuffer[srcIdx];
        }
      }
      DebugSerial.println("[MIC] Command capture started (listening for voice command)...");
      updateOledUI("MIC LISTENING", "", "Act: Recording Voice", true);
      broadcastStatus("recording", "Recording audio from INMP441...");
    }

    // With streaming openWakeWord, idle speech is not sent to Whisper. Once
    // awake, the same adaptive VAD endpoints only the actual command.
    if (!isRecordingVoice && !isTranscribing && !isSpeakerPlaying) {
      bool canCapture = !remoteWakeAvailable || !triggerWordEnabled ||
                        assistantState == STATE_LISTENING_FOR_COMMAND;
      if (canCapture && millis() > 4000 && millis() >= listenNotBefore && WiFi.status() == WL_CONNECTED) {
        if (rms > startThreshold) {
          speechStartCount++;
        } else {
          speechStartCount = 0;
        }
        if (speechStartCount >= VAD_START_FRAMES) {
          isRecordingVoice = true;
          currentSampleCount = 0;
          silenceCount = 0;
          speechStartCount = 0;

          // Copy 250ms pre-roll buffer into recordBuffer.
          if (recordBuffer) {
            for (size_t k = 0; k < PREROLL_SAMPLES; k++) {
              size_t srcIdx = (preRollIndex + k) % PREROLL_SAMPLES;
              recordBuffer[currentSampleCount++] = preRollBuffer[srcIdx];
            }
          }

          DebugSerial.printf("[VAD] Voice detected (RMS %.1f, floor %.1f, start %.1f). Capturing %s...\n",
                        rms, adaptiveNoiseFloor, startThreshold,
                        (assistantState == STATE_LISTENING_FOR_COMMAND) ? "command" : "Whisper fallback");
          updateOledUI("MIC LISTENING", "", "Act: Recording Voice", true);
          broadcastStatus("recording", "Voice detected on INMP441");
        }
      }
    }

    // Accumulate samples during recording
    if (isRecordingVoice && recordBuffer) {
      for (size_t i = 0; i < samplesRead; i++) {
        if (currentSampleCount < MAX_RECORD_SAMPLES) {
          recordBuffer[currentSampleCount++] = pcmChunk[i];
        }
      }

      if (rms < stopThreshold) {
        silenceCount++;
      } else {
        silenceCount = 0;
      }

      // Snappy cutoff: Stop as soon as speech + short silence is reached
      if ((silenceCount >= VAD_SILENCE_FRAMES && currentSampleCount >= MIN_RECORD_SAMPLES) ||
          currentSampleCount >= MAX_RECORD_SAMPLES) {
        isRecordingVoice = false;
        silenceCount = 0;

        DebugSerial.printf("[MIC] Speech capture finished (%u samples, %.2fs). Dispatching to Whisper STT...\n",
                      (unsigned int)currentSampleCount, (float)currentSampleCount / MIC_SAMPLE_RATE);

        if (voiceQueue && currentSampleCount >= 4000) {
          isTranscribing = true;
          VoiceRecordMsg vmsg;
          vmsg.pcmData = recordBuffer;
          vmsg.sampleCount = currentSampleCount;
          if (xQueueSend(voiceQueue, &vmsg, 0) != pdTRUE) {
            isTranscribing = false;
          }
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Voice Pipeline Diagnostics & WebSocket Status Broadcasting
// ---------------------------------------------------------------------------

const char* voicePhaseName() {
  if (voiceResetRequested) return "resetting";
  if (isTranscribing) return "transcribing";
  if (isRecordingVoice) return "recording_command";
  if (isSpeakerPlaying) return "playing_feedback";
  if (assistantState == STATE_LISTENING_FOR_COMMAND) {
    if ((long)(millis() - listenNotBefore) < 0) return "wake_settling";
    return "waiting_for_command";
  }
  if (!triggerWordEnabled) return "wake_disabled";
  return remoteWakeAvailable ? "waiting_for_wake" : "whisper_fallback";
}

unsigned long commandWindowRemainingMs() {
  if (assistantState != STATE_LISTENING_FOR_COMMAND || commandWindowExpiry == 0) return 0;
  long remaining = (long)(commandWindowExpiry - millis());
  return remaining > 0 ? (unsigned long)remaining : 0;
}

void resetVoicePipeline(const char* reason) {
  voiceResetRequested = true;
  remoteWakeDetected = false;
  manualRecordRequested = false;
  isRecordingVoice = false;
  assistantState = STATE_IDLE_WAIT_WAKE;
  commandWindowExpiry = 0;
  listenNotBefore = millis() + WAKE_SETTLE_MS;
  resetPreRollRequested = true;

  DebugSerial.printf("[VOICE RESET] %s\n", reason);
  updateOledUI("VOICE SATELLITE", lastSpeechHeard.c_str(), "Act: Voice Pipeline Reset");

  // A running Whisper request observes this flag and exits. With no request
  // active, the reset is complete immediately.
  if (!isTranscribing) voiceResetRequested = false;
  broadcastStatus("idle", reason);
}

void broadcastStatus(const char* state, const char* detail) {
  JsonDocument doc;
  doc["type"] = "status";
  doc["state"] = state;
  doc["detail"] = detail;
  doc["volume"] = (int)(currentVolume * 100);
  doc["ip"] = deviceIP;
  doc["mode"] = (currentMode == MODE_SMART_HOME) ? "smart_home" : "media";
  doc["screenText"] = lastOledMessage;
  doc["speechHeard"] = lastSpeechHeard;
  doc["triggerWord"] = triggerWord;
  doc["triggerEnabled"] = triggerWordEnabled;
  doc["wakeEngine"] = remoteWakeAvailable ? "openWakeWord" : "Whisper fallback";
  doc["voicePhase"] = voicePhaseName();
  doc["wakeStreamConnected"] = wakeStreamConnected;
  doc["speakerPlaying"] = isSpeakerPlaying;
  doc["recording"] = isRecordingVoice;
  doc["transcribing"] = isTranscribing;
  doc["commandWindowRemainingMs"] = commandWindowRemainingMs();
  doc["uptimeMs"] = millis();
  doc["vadThreshold"] = vadThreshold;
  doc["noiseFloor"] = (int)adaptiveNoiseFloor;
  doc["haLight"] = haDefaultLight;
  doc["haServer"] = haServerIP + ":" + String(haServerPort);
  String output;
  serializeJson(doc, output);
  ws.textAll(output);
}

void broadcastDiagnostics(bool includeLogs) {
  JsonDocument doc;
  doc["type"] = "diagnostics";
  doc["voicePhase"] = voicePhaseName();
  doc["wakeStreamConnected"] = wakeStreamConnected;
  doc["speakerPlaying"] = isSpeakerPlaying;
  doc["recording"] = isRecordingVoice;
  doc["transcribing"] = isTranscribing;
  doc["commandWindowRemainingMs"] = commandWindowRemainingMs();
  doc["uptimeMs"] = millis();
  if (includeLogs) doc["logs"] = diagnosticLogSnapshot();
  String output;
  serializeJson(doc, output);
  ws.textAll(output);
}

// ---------------------------------------------------------------------------
// OLED Display Functions (mutex-protected for thread safety)
// ---------------------------------------------------------------------------

void updateOledUI(const char* titleBanner, const char* speechText, const char* actionText, bool isInterim) {
  if (!oledReady) return;
  if (xSemaphoreTake(oledMutex, pdMS_TO_TICKS(100)) != pdTRUE) return;

  if (titleBanner && strlen(titleBanner) > 0) lastOledTitle = String(titleBanner);
  if (speechText && strlen(speechText) > 0 && !isInterim) {
    lastSpeechHeard = String(speechText);
    lastOledMessage = String(speechText);
  }
  if (actionText && strlen(actionText) > 0) {
    currentActionText = String(actionText);
  }

  display.clearDisplay();

  // 1. Inverted Header Banner (y = 0..11)
  display.fillRect(0, 0, SCREEN_WIDTH, 11, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
  display.setTextSize(1);
  display.setTextWrap(false);
  display.setCursor(4, 2);
  display.print(titleBanner && strlen(titleBanner) > 0 ? titleBanner : "VOICE SATELLITE");

  // 2. Main Body: Voice Command / Microphone Speech (y = 14..48)
  display.setTextColor(SSD1306_WHITE);

  String speech = (speechText && strlen(speechText) > 0) ? String(speechText) : lastSpeechHeard;
  speech.trim();

  if (speech.length() == 0 || (isInterim && speech == "...")) {
    if (isInterim) {
      display.setTextSize(1);
      display.setTextWrap(true);
      display.setCursor(4, 18);
      display.print("Recording voice...");
      display.setCursor(4, 30);
      display.print("Listening on mic...");
      for (int i = 0; i < 7; i++) {
        int h = 4 + (i % 3) * 4;
        display.fillRect(48 + i * 5, 43 - h / 2, 3, h, SSD1306_WHITE);
      }
    } else {
      display.setTextSize(1);
      display.setTextWrap(true);
      display.setCursor(4, 18);
      display.print("Speak now...");
      display.setCursor(4, 30);
      display.print("Voice commands active");
      for (int i = 0; i < 7; i++) {
        int h = 3 + ((i * 3) % 7);
        display.fillRect(48 + i * 5, 43 - h / 2, 3, h, SSD1306_WHITE);
      }
    }
  } else {
    // Show voice command heard from microphone
    int len = speech.length();
    if (len <= 13 && speech.indexOf('\n') < 0) {
      display.setTextSize(2);
      display.setTextWrap(false);
      display.setCursor(2, 20);
      display.print(speech);
    } else {
      display.setTextSize(1);
      display.setTextWrap(true);
      display.setCursor(2, 16);
      display.print(speech);
    }
  }

  // 3. Divider Line at y = 50
  display.drawLine(0, 50, SCREEN_WIDTH, 50, SSD1306_WHITE);

  // 4. Bottom Footer: Really small action of what is happening right now (y = 53..63)
  display.setTextSize(1);
  display.setTextWrap(false);
  display.setCursor(2, 54);

  String act = (actionText && strlen(actionText) > 0) ? String(actionText) : currentActionText;
  if (!act.startsWith("Act:") && !act.startsWith("Action:")) {
    act = "Act: " + act;
  }
  if (act.length() > 21) {
    act = act.substring(0, 19) + "..";
  }
  display.print(act);

  display.display();
  xSemaphoreGive(oledMutex);
}

void renderDisplay(const char* title, const char* line1, const char* line2) {
  updateOledUI(title, line1, line2, false);
}

void renderCustomMessage(const char* title, const char* message) {
  updateOledUI(title, message, "Ready", false);
}

void renderSpeechDisplay(const char* text, bool isInterim, const char* statusMsg) {
  const char* banner = isInterim ? "LISTENING..." : "VOICE SATELLITE";
  updateOledUI(banner, text, statusMsg, isInterim);
}

void renderSmartHomeDisplay(const char* actionTitle, const char* target, const char* statusMsg) {
  String t = String(target);
  if (t.startsWith("light.")) t = t.substring(6);
  if (t == "h6076") t = "Lamp 1";
  else if (t == "h6076_2") t = "Lamp 2";
  else if (t == "all_lamps") t = "All Lamps";

  String act = String(actionTitle) + ": " + t;
  updateOledUI("VOICE COMMAND", lastSpeechHeard.c_str(), act.c_str(), false);
}

// ---------------------------------------------------------------------------
// Audio Playback Functions (Core 1 audio task)
// ---------------------------------------------------------------------------

void playToneRaw(float freqHz, int durationMs) {
  if (freqHz <= 0 || currentVolume <= 0.001f || stopRequested) {
    delay(durationMs);
    return;
  }

  int totalSamples = (SAMPLE_RATE * durationMs) / 1000;
  const int bufferSize = 128;
  int16_t buffer[bufferSize * 2];

  float phase = 0.0f;
  float phaseIncrement = (2.0f * M_PI * freqHz) / SAMPLE_RATE;
  int16_t amplitude = (int16_t)(30000.0f * currentVolume);

  int samplesWritten = 0;
  while (samplesWritten < totalSamples && !stopRequested) {
    int chunk = min(bufferSize, totalSamples - samplesWritten);
    for (int i = 0; i < chunk; i++) {
      int16_t val = (int16_t)(sin(phase) * amplitude);
      buffer[i * 2]     = val;
      buffer[i * 2 + 1] = val;
      phase += phaseIncrement;
      if (phase >= 2.0f * M_PI) phase -= 2.0f * M_PI;
    }
    size_t written = 0;
    i2s_write(I2S_PORT_SPEAKER, buffer, chunk * 2 * sizeof(int16_t), &written, pdMS_TO_TICKS(100));
    samplesWritten += chunk;
  }
  i2s_zero_dma_buffer(I2S_PORT_SPEAKER);
}

void playChimeAudio() {
  updateOledUI("VOICE SATELLITE", lastSpeechHeard.c_str(), "Act: Wake Chime");
  broadcastStatus("playing", "Wake Chime");
  playToneRaw(523.25f, 130);
  if (!stopRequested) { delay(25); playToneRaw(659.25f, 130); }
  if (!stopRequested) { delay(25); playToneRaw(783.99f, 300); }
}

void playWakeEarconAudio() {
  updateOledUI("WAKE DETECTED", "Hey Burden", "Act: Wake Confirmed");
  broadcastStatus("playing", "Wake earcon");
  playToneRaw(880.0f, 42);
  if (!stopRequested) playToneRaw(1174.66f, 58);
}

void playCoinAudio() {
  updateOledUI("VOICE SATELLITE", lastSpeechHeard.c_str(), "Act: Mario Coin");
  broadcastStatus("playing", "Mario Coin");
  playToneRaw(987.77f, 90);
  if (!stopRequested) playToneRaw(1318.51f, 350);
}

void playFanfareAudio() {
  updateOledUI("VOICE SATELLITE", lastSpeechHeard.c_str(), "Act: Fanfare Melody");
  broadcastStatus("playing", "Fanfare");
  float notes[] = {523.25f, 587.33f, 659.25f, 880.0f, 783.99f};
  int durations[] = {120, 120, 120, 220, 450};
  for (int i = 0; i < 5 && !stopRequested; i++) {
    playToneRaw(notes[i], durations[i]);
    if (!stopRequested) delay(35);
  }
}

void playSweepAudio() {
  updateOledUI("VOICE SATELLITE", lastSpeechHeard.c_str(), "Act: Frequency Sweep");
  broadcastStatus("playing", "Frequency Sweep");

  const int totalSamples = (SAMPLE_RATE * 700) / 1000;
  const int bufferSize = 128;
  int16_t buffer[bufferSize * 2];
  float phase = 0.0f;
  int16_t amplitude = (int16_t)(30000.0f * currentVolume);

  for (int s = 0; s < totalSamples && !stopRequested; s += bufferSize) {
    int chunk = min(bufferSize, totalSamples - s);
    for (int i = 0; i < chunk; i++) {
      float progress = (float)(s + i) / (float)totalSamples;
      float freq;
      if (progress < 0.5f) {
        freq = 300.0f + (1600.0f - 300.0f) * (progress * 2.0f);
      } else {
        freq = 1600.0f - (1600.0f - 300.0f) * ((progress - 0.5f) * 2.0f);
      }
      float phaseInc = (2.0f * M_PI * freq) / SAMPLE_RATE;
      int16_t val = (int16_t)(sin(phase) * amplitude);
      buffer[i * 2]     = val;
      buffer[i * 2 + 1] = val;
      phase += phaseInc;
      if (phase >= 2.0f * M_PI) phase -= 2.0f * M_PI;
    }
    size_t written = 0;
    i2s_write(I2S_PORT_SPEAKER, buffer, chunk * 2 * sizeof(int16_t), &written, pdMS_TO_TICKS(100));
  }
  i2s_zero_dma_buffer(I2S_PORT_SPEAKER);
}

// Low-Latency Direct Neural TTS Audio Streamer
void streamRealVoiceTTS(const char* text) {
  if (stopRequested) return;

  String encodedText = "";
  for (unsigned int i = 0; i < strlen(text); i++) {
    char c = text[i];
    if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
      encodedText += c;
    } else if (c == ' ') {
      encodedText += "+";
    } else {
      char hex[4];
      sprintf(hex, "%%%02X", (unsigned char)c);
      encodedText += hex;
    }
  }

  String ttsUrl = "http://" + haServerIP + ":" + String(TTS_PORT) + "/tts?text=" + encodedText;

  updateOledUI("TTS PLAYING", text, "Act: Piper TTS Stream");
  broadcastStatus("playing", text);

  HTTPClient http;
  http.setReuse(true);
  http.begin(ttsUrl);
  http.setTimeout(8000);

  int httpCode = http.GET();
  if (httpCode == HTTP_CODE_OK && !stopRequested) {
    int totalLen = http.getSize();
    WiFiClient* stream = http.getStreamPtr();
    stream->setNoDelay(true);

    uint8_t header[44];
    int headerRead = 0;
    unsigned long startHdr = millis();
    while (headerRead < 44 && (millis() - startHdr < 2000) && !stopRequested) {
      if (stream->available() > 0) {
        int r = stream->readBytes(header + headerRead, 44 - headerRead);
        if (r > 0) headerRead += r;
      } else {
        delay(1);
      }
    }

    if (headerRead >= 44 && !stopRequested) {
      uint32_t sampleRate = header[24] | (header[25] << 8) | (header[26] << 16) | (header[27] << 24);
      if (sampleRate < 8000 || sampleRate > 48000) sampleRate = 22050;

      i2s_set_sample_rates(I2S_PORT_SPEAKER, sampleRate);

      const size_t RAW_CHUNK = 512;
      uint8_t rawBuf[RAW_CHUNK];
      int16_t outBuf[RAW_CHUNK];

      int remaining = (totalLen > 44) ? (totalLen - 44) : 1000000;
      unsigned long lastDataTime = millis();

      while (stream->available() < 1024 && (millis() - lastDataTime < 300) && http.connected()) {
        delay(1);
      }

      while (remaining > 0 && (millis() - lastDataTime < 3000) && !stopRequested) {
        size_t avail = stream->available();
        if (avail >= 2) {
          lastDataTime = millis();
          int toRead = min((size_t)min((int)RAW_CHUNK, remaining), avail);
          toRead &= ~1;

          int r = stream->readBytes(rawBuf, toRead);
          if (r > 0) {
            r &= ~1;
            int numSamples = r / 2;
            int16_t* inSamples = (int16_t*)rawBuf;
            for (int k = 0; k < numSamples; k++) {
              int32_t sampleVal = (int32_t)(inSamples[k] * currentVolume);
              if (sampleVal > 32767) sampleVal = 32767;
              else if (sampleVal < -32768) sampleVal = -32768;

              int16_t s = (int16_t)sampleVal;
              outBuf[k * 2]     = s;
              outBuf[k * 2 + 1] = s;
            }
            size_t written = 0;
            i2s_write(I2S_PORT_SPEAKER, outBuf, numSamples * 2 * sizeof(int16_t), &written, pdMS_TO_TICKS(100));
            remaining -= r;
          }
        } else {
          if (!http.connected() && avail == 0) break;
          delay(1);
        }
      }

      i2s_zero_dma_buffer(I2S_PORT_SPEAKER);
      i2s_set_sample_rates(I2S_PORT_SPEAKER, SAMPLE_RATE);
    }
    http.end();
  } else {
    http.end();
    if (!stopRequested) {
      renderDisplay("HA VOICE HUB", "TTS Stream Error", ("HTTP " + String(httpCode)).c_str());
      broadcastStatus("error", "TTS request failed");
      delay(1000);
    }
  }
}

// ---------------------------------------------------------------------------
// FreeRTOS Audio Task — Core 1
// ---------------------------------------------------------------------------

void audioTaskFunction(void* param) {
  AudioCommand cmd;
  for (;;) {
    if (xQueueReceive(audioQueue, &cmd, portMAX_DELAY) == pdTRUE) {
      isSpeakerPlaying = true;

      if (cmd.type == CMD_STOP) {
        AudioCommand discard;
        while (xQueueReceive(audioQueue, &discard, 0) == pdTRUE) {}
        i2s_zero_dma_buffer(I2S_PORT_SPEAKER);
        stopRequested = false;
        isSpeakerPlaying = false;
        updateOledUI(lastOledTitle.c_str(), lastSpeechHeard.c_str(), "Act: Audio Stopped");
        broadcastStatus("idle", "Stopped");
        continue;
      }

      stopRequested = false;

      switch (cmd.type) {
        case CMD_WAKE_EARCON: playWakeEarconAudio(); break;
        case CMD_CHIME:       playChimeAudio(); break;
        case CMD_COIN:        playCoinAudio(); break;
        case CMD_FANFARE:     playFanfareAudio(); break;
        case CMD_SWEEP:       playSweepAudio(); break;
        case CMD_SPEAK_VOICE: streamRealVoiceTTS(cmd.text); break;
        default: break;
      }

      isSpeakerPlaying = false;

      // Discard all speaker-contaminated pre-roll and arm adaptive VAD only
      // after a short acoustic settling guard. The command window starts now.
      if (cmd.type == CMD_WAKE_EARCON && assistantState == STATE_LISTENING_FOR_COMMAND) {
        resetPreRollRequested = true;
        listenNotBefore = millis() + WAKE_SETTLE_MS;
        commandWindowExpiry = listenNotBefore + COMMAND_LISTEN_MS;
      }

      if (!stopRequested) {
        if (assistantState == STATE_LISTENING_FOR_COMMAND) {
          updateOledUI("WAKE DETECTED", "Hey Burden", "Act: Listening for Command");
        } else {
          updateOledUI(lastOledTitle.c_str(), lastSpeechHeard.c_str(), "Act: Ready");
        }
        broadcastStatus("idle", "Ready");
      }
    }
  }
}

// ---------------------------------------------------------------------------
// WebSocket Event Handler
// ---------------------------------------------------------------------------

void onWsEvent(AsyncWebSocket* ws, AsyncWebSocketClient* client,
               AwsEventType type, void* arg, uint8_t* data, size_t len) {

  if (type == WS_EVT_CONNECT) {
    DebugSerial.printf("[WS] Client #%u connected\n", client->id());
    JsonDocument doc;
    doc["type"] = "status";
    doc["state"] = "idle";
    doc["detail"] = "Connected";
    doc["volume"] = (int)(currentVolume * 100);
    doc["ip"] = deviceIP;
    doc["mode"] = (currentMode == MODE_SMART_HOME) ? "smart_home" : "media";
    doc["screenText"] = lastOledMessage;
    doc["speechHeard"] = lastSpeechHeard;
    doc["triggerWord"] = triggerWord;
    doc["triggerEnabled"] = triggerWordEnabled;
    doc["wakeEngine"] = remoteWakeAvailable ? "openWakeWord" : "Whisper fallback";
    doc["voicePhase"] = voicePhaseName();
    doc["wakeStreamConnected"] = wakeStreamConnected;
    doc["speakerPlaying"] = isSpeakerPlaying;
    doc["recording"] = isRecordingVoice;
    doc["transcribing"] = isTranscribing;
    doc["commandWindowRemainingMs"] = commandWindowRemainingMs();
    doc["uptimeMs"] = millis();
    doc["vadThreshold"] = vadThreshold;
    doc["noiseFloor"] = (int)adaptiveNoiseFloor;
    doc["haLight"] = haDefaultLight;
    doc["haServer"] = haServerIP + ":" + String(haServerPort);
    String output;
    serializeJson(doc, output);
    client->text(output);
  }

  else if (type == WS_EVT_DISCONNECT) {
    DebugSerial.printf("[WS] Client #%u disconnected\n", client->id());
  }

  else if (type == WS_EVT_DATA) {
    AwsFrameInfo* info = (AwsFrameInfo*)arg;
    if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) {
      JsonDocument doc;
      DeserializationError err = deserializeJson(doc, data, len);
      if (err) return;

      const char* action = doc["action"] | "";

      // 1. Switch Mode
      if (strcmp(action, "set_mode") == 0) {
        const char* mode = doc["mode"] | "smart_home";
        if (strcmp(mode, "media") == 0) {
          currentMode = MODE_MEDIA;
          broadcastStatus("idle", "Switched to Media & Voice Mode");
        } else {
          currentMode = MODE_SMART_HOME;
          broadcastStatus("idle", "Switched to Smart Home Automation");
        }
      }

      // 2. Direct Smart Home Light Action
      else if (strcmp(action, "smart_home_light") == 0) {
        const char* lAction = doc["light_action"] | "toggle";
        const char* entity = doc["entity"] | haDefaultLight.c_str();

        bool ok = sendHomeAssistantLightCommand(lAction, entity);
        String actStr = (strcmp(lAction, "turn_on") == 0) ? "LIGHTS ON" : ((strcmp(lAction, "turn_off") == 0) ? "LIGHTS OFF" : "TOGGLE LIGHT");
        renderSmartHomeDisplay(actStr.c_str(), entity, ok ? "Executed via HA" : "HA Request Sent");

        if (strcmp(lAction, "turn_on") == 0 || strcmp(lAction, "toggle") == 0) {
          AudioCommand soundCmd = { CMD_COIN, "" };
          xQueueSend(audioQueue, &soundCmd, 0);
        } else {
          AudioCommand soundCmd = { CMD_CHIME, "" };
          xQueueSend(audioQueue, &soundCmd, 0);
        }

        JsonDocument resDoc;
        resDoc["type"] = "smart_home_action";
        resDoc["action"] = lAction;
        resDoc["target"] = entity;
        resDoc["success"] = ok;
        resDoc["message"] = actStr + " " + String(entity);
        String out;
        serializeJson(resDoc, out);
        ws->textAll(out);
      }

      // 3. Update Trigger Word Settings
      else if (strcmp(action, "set_trigger_word") == 0) {
        if (doc["word"].is<const char*>()) {
          triggerWord = String((const char*)doc["word"]);
          triggerWord.toLowerCase();
          triggerWord.trim();
        }
        if (doc["enabled"].is<bool>()) {
          triggerWordEnabled = doc["enabled"].as<bool>();
        }
        broadcastStatus("idle", ("Trigger Word: " + triggerWord + (triggerWordEnabled ? " (Active)" : " (Disabled)")).c_str());
      }

      // 4. Update Home Assistant Configuration
      else if (strcmp(action, "set_ha_config") == 0) {
        if (doc["ip"].is<const char*>()) haServerIP = String((const char*)doc["ip"]);
        if (doc["port"].is<int>()) haServerPort = doc["port"].as<int>();
        if (doc["token"].is<const char*>()) haApiToken = String((const char*)doc["token"]);
        if (doc["entity"].is<const char*>()) haDefaultLight = String((const char*)doc["entity"]);
        broadcastStatus("idle", "Home Assistant configuration updated");
      }

      // 5. Simulated Spoken Voice Command
      else if (strcmp(action, "test_voice") == 0 || strcmp(action, "voice_command") == 0) {
        const char* text = doc["text"] | "";
        if (strlen(text) > 0) {
          lastSpeechHeard = text;
          SmartHomeResult res = parseAndExecuteVoiceCommand(text);
          if (res.handled) {
            updateOledUI((res.action == "WAKE_WORD") ? "WAKE DETECTED" : "VOICE COMMAND", text, ("Act: " + res.message).c_str());
            JsonDocument resDoc;
            resDoc["type"] = "smart_home_action";
            resDoc["action"] = res.action;
            resDoc["target"] = res.target;
            resDoc["success"] = res.success;
            resDoc["message"] = res.message;
            resDoc["transcript"] = text;
            String out;
            serializeJson(resDoc, out);
            ws->textAll(out);
          } else {
            updateOledUI("VOICE COMMAND", text, "Act: Voice Recognized");
          }
        }
      }

      // 6. Custom OLED Display Message
      else if (strcmp(action, "display") == 0) {
        const char* text = doc["text"] | "";
        const char* title = doc["title"] | "OLED MESSAGE";
        renderCustomMessage(title, text);
        broadcastStatus("idle", "Text updated on OLED");
      }

      // 7. Clear OLED Screen
      else if (strcmp(action, "clear_display") == 0) {
        lastSpeechHeard = "";
        updateOledUI("VOICE SATELLITE", "", "Act: Screen Reset");
        broadcastStatus("idle", "Display reset");
      }

      // 7. Sound Effects
      else if (strcmp(action, "play") == 0) {
        const char* sound = doc["sound"] | "";
        AudioCommand cmd;
        cmd.text[0] = '\0';

        if (strcmp(sound, "chime") == 0)        cmd.type = CMD_CHIME;
        else if (strcmp(sound, "coin") == 0)     cmd.type = CMD_COIN;
        else if (strcmp(sound, "fanfare") == 0)  cmd.type = CMD_FANFARE;
        else if (strcmp(sound, "sweep") == 0)    cmd.type = CMD_SWEEP;
        else return;

        AudioCommand discard;
        while (xQueueReceive(audioQueue, &discard, 0) == pdTRUE) {}
        xQueueSend(audioQueue, &cmd, 0);
      }

      // 8. Neural TTS Voice Speech
      else if (strcmp(action, "speak") == 0) {
        const char* text = doc["text"] | "";
        if (strlen(text) == 0 || strlen(text) > 190) return;

        AudioCommand cmd;
        cmd.type = CMD_SPEAK_VOICE;
        strncpy(cmd.text, text, sizeof(cmd.text) - 1);
        cmd.text[sizeof(cmd.text) - 1] = '\0';

        stopRequested = true;
        AudioCommand discard;
        while (xQueueReceive(audioQueue, &discard, 0) == pdTRUE) {}
        xQueueSend(audioQueue, &cmd, 0);
      }

      // 9. Volume Adjustment
      else if (strcmp(action, "volume") == 0) {
        int val = doc["value"] | -1;
        if (val < 5 || val > 100) return;
        currentVolume = (float)val / 100.0f;
        updateOledUI(lastOledTitle.c_str(), lastSpeechHeard.c_str(), ("Act: Vol " + String(val) + "%").c_str());
        broadcastStatus("volume", ("Volume: " + String(val) + "%").c_str());
      }

      // 10. Stop Audio
      else if (strcmp(action, "stop") == 0) {
        stopRequested = true;
        AudioCommand cmd;
        cmd.type = CMD_STOP;
        cmd.text[0] = '\0';
        AudioCommand discard;
        while (xQueueReceive(audioQueue, &discard, 0) == pdTRUE) {}
        xQueueSend(audioQueue, &cmd, 0);
      }

      // 11. Recover wake/VAD/STT state without rebooting the device.
      else if (strcmp(action, "reset_voice_pipeline") == 0) {
        resetVoicePipeline("Manual dashboard reset — ready for 'Hey Burden'");
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Dual I2S Initialization (Speaker on I2S_0, Mic on I2S_1)
// ---------------------------------------------------------------------------

void initI2SSpeaker() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
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
    .bck_io_num = I2S_SPEAKER_BCLK,
    .ws_io_num = I2S_SPEAKER_LRC,
    .data_out_num = I2S_SPEAKER_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_PORT_SPEAKER, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT_SPEAKER, &pin_config);
  i2s_zero_dma_buffer(I2S_PORT_SPEAKER);
  DebugSerial.println("[I2S] MAX98357A Speaker TX (I2S_NUM_0) initialized.");
}

void initI2SMic() {
  i2s_config_t i2s_mic_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = MIC_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t mic_pin_config = {
    .bck_io_num = I2S_MIC_SCK,
    .ws_io_num = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_MIC_SD
  };

  esp_err_t err = i2s_driver_install(I2S_PORT_MIC, &i2s_mic_config, 0, NULL);
  if (err == ESP_OK) {
    i2s_set_pin(I2S_PORT_MIC, &mic_pin_config);
    DebugSerial.println("[I2S] INMP441 Microphone RX (I2S_NUM_1) initialized.");
  } else {
    DebugSerial.printf("[I2S] Mic RX Init failed: %d\n", err);
  }
}

// ---------------------------------------------------------------------------
// Embedded Dashboard HTML with 3-Tab Smart Home & Voice Satellite UI
// ---------------------------------------------------------------------------

// Dashboard HTML is stored gzip-compressed in include/dashboard_gz.h.

// ---------------------------------------------------------------------------
// Wi-Fi Event Handler (Non-blocking Standalone Auto-Reconnect)
// ---------------------------------------------------------------------------

void onWiFiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      deviceIP = WiFi.localIP().toString();
      DebugSerial.printf("[WiFi] Connected! IP: %s\n", deviceIP.c_str());
      updateOledUI(lastOledTitle.c_str(), lastSpeechHeard.c_str(), ("Act: IP " + deviceIP).c_str());
      broadcastStatus("idle", ("Connected to Wi-Fi: " + deviceIP).c_str());
      break;

    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      DebugSerial.println("[WiFi] Disconnected! Reconnecting in background...");
      deviceIP = "Reconnecting...";
      updateOledUI(lastOledTitle.c_str(), lastSpeechHeard.c_str(), "Act: Wi-Fi Reconnecting");
      WiFi.reconnect();
      break;

    default:
      break;
  }
}

// ---------------------------------------------------------------------------
// Setup — Dual I2S, OLED, Server, Tasks
// ---------------------------------------------------------------------------

void setup() {
  delay(500);

  DebugSerial.begin(115200);
  DebugSerial.println("\n==============================================");
  DebugSerial.println("  ESP32-S3 Voice Satellite & Smart Home v2.1  ");
  DebugSerial.println("==============================================");

  oledMutex = xSemaphoreCreateMutex();
  audioQueue = xQueueCreate(4, sizeof(AudioCommand));
  voiceQueue = xQueueCreate(4, sizeof(VoiceRecordMsg));
  haSyncQueue = xQueueCreate(6, sizeof(HaSyncCommand));
  wakeAudioQueue = xQueueCreate(8, sizeof(WakeAudioFrame));

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);

  // Probe I2C address (0x3C default, 0x3D fallback)
  uint8_t oledAddress = 0x3C;
  Wire.beginTransmission(0x3C);
  if (Wire.endTransmission() != 0) {
    Wire.beginTransmission(0x3D);
    if (Wire.endTransmission() == 0) {
      oledAddress = 0x3D;
      DebugSerial.println("[OLED] Found SSD1306 at I2C address 0x3D");
    } else {
      DebugSerial.println("[OLED] Warning: No I2C response at 0x3C or 0x3D");
    }
  } else {
    DebugSerial.println("[OLED] Found SSD1306 at I2C address 0x3C");
  }

  if (display.begin(SSD1306_SWITCHCAPVCC, oledAddress)) {
    oledReady = true;
    display.clearDisplay();
    display.setTextWrap(true);
    DebugSerial.printf("[OLED] Display initialized successfully at 0x%02X\n", oledAddress);
    updateOledUI("VOICE SATELLITE", "", "Act: Connecting Wi-Fi...");
  } else {
    uint8_t altAddr = (oledAddress == 0x3C) ? 0x3D : 0x3C;
    if (display.begin(SSD1306_SWITCHCAPVCC, altAddr)) {
      oledReady = true;
      display.clearDisplay();
      display.setTextWrap(true);
      DebugSerial.printf("[OLED] Display initialized on alternate 0x%02X\n", altAddr);
      updateOledUI("VOICE SATELLITE", "", "Act: Connecting Wi-Fi...");
    } else {
      DebugSerial.println("[OLED] SSD1306 initialization failed on both addresses!");
    }
  }

  // Initialize Dual I2S Controllers
  initI2SSpeaker();
  initI2SMic();

  // Register Wi-Fi
  WiFi.onEvent(onWiFiEvent);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 30) {
    delay(300);
    DebugSerial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    WiFi.setSleep(false);
    deviceIP = WiFi.localIP().toString();
    DebugSerial.printf("\n[OK] Wi-Fi Connected! IP: %s\n", deviceIP.c_str());
    updateOledUI("VOICE SATELLITE", "", ("Act: IP " + deviceIP).c_str());
  } else {
    deviceIP = "No Wi-Fi";
    DebugSerial.println("\n[!] Wi-Fi connection timed out. Background reconnect active.");
    updateOledUI("VOICE SATELLITE", "", "Act: Wi-Fi Reconnecting");
  }

  // WebSocket
  ws.onEvent(onWsEvent);
  server.addHandler(&ws);

  // Serve Main Dashboard
  server.on("/", HTTP_GET, [](AsyncWebServerRequest* request) {
    AsyncWebServerResponse* response = request->beginResponse(
      200, "text/html; charset=utf-8", dashboard_html_gz, dashboard_html_gz_len);
    response->addHeader("Content-Encoding", "gzip");
    response->addHeader("Cache-Control", "no-store");
    response->addHeader("Connection", "close");
    request->send(response);
  });

  // Lightweight diagnostics remain usable even if dashboard JavaScript fails.
  server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest* request) {
    JsonDocument doc;
    doc["volume"] = (int)(currentVolume * 100);
    doc["wakeEngine"] = remoteWakeAvailable ? "openWakeWord" : "Whisper fallback";
    doc["voicePhase"] = voicePhaseName();
    doc["wakeStreamConnected"] = wakeStreamConnected;
    doc["speakerPlaying"] = isSpeakerPlaying;
    doc["recording"] = isRecordingVoice;
    doc["transcribing"] = isTranscribing;
    doc["commandWindowRemainingMs"] = commandWindowRemainingMs();
    doc["vadThreshold"] = vadThreshold;
    doc["noiseFloor"] = (int)adaptiveNoiseFloor;
    doc["uptimeMs"] = millis();
    String output;
    serializeJson(doc, output);
    AsyncWebServerResponse* response = request->beginResponse(200, "application/json", output);
    response->addHeader("Cache-Control", "no-store");
    response->addHeader("Connection", "close");
    request->send(response);
  });

  server.on("/api/logs", HTTP_GET, [](AsyncWebServerRequest* request) {
    AsyncWebServerResponse* response = request->beginResponse(200, "text/plain; charset=utf-8", diagnosticLogSnapshot());
    response->addHeader("Cache-Control", "no-store");
    response->addHeader("Connection", "close");
    request->send(response);
  });

  // Web OTA Firmware Update Endpoints
  server.on("/update", HTTP_GET, [](AsyncWebServerRequest* request) {
    const char* otaHtml = R"rawliteral(
<!DOCTYPE html><html><head><meta charset="utf-8"><title>ESP32-S3 OTA Update</title>
<style>body{font-family:sans-serif;background:#090d16;color:#f1f5f9;display:flex;justify-content:center;padding:40px}
.card{background:#121829;padding:24px;border-radius:12px;max-width:420px;width:100%;border:1px solid rgba(255,255,255,0.1)}
h2{margin-top:0;font-size:1.2rem}p{color:#94a3b8;font-size:0.85rem}
input[type=file]{margin:16px 0;color:#94a3b8;display:block}
button{background:#38bdf8;color:#090d16;border:none;padding:11px 20px;font-weight:bold;border-radius:8px;cursor:pointer}
button:hover{background:#0ea5e9}</style></head>
<body><div class="card"><h2>⚡ Wi-Fi Firmware Update</h2>
<p>Select your compiled <code>firmware.bin</code> to flash over Wi-Fi:</p>
<form method="POST" action="/update" enctype="multipart/form-data">
<input type="file" name="update" required>
<button type="submit">Flash over Wi-Fi</button></form></div></body></html>
)rawliteral";
    request->send(200, "text/html", otaHtml);
  });

  server.on("/update", HTTP_POST, [](AsyncWebServerRequest *request) {
    bool shouldReboot = !Update.hasError();
    AsyncWebServerResponse *response = request->beginResponse(200, "text/plain", shouldReboot ? "OK - Update Successful! Rebooting ESP32..." : "FAIL - Update Failed!");
    response->addHeader("Connection", "close");
    request->send(response);
    if (shouldReboot) {
      delay(800);
      ESP.restart();
    }
  }, [](AsyncWebServerRequest *request, String filename, size_t index, uint8_t *data, size_t len, bool final) {
    if (!index) {
      DebugSerial.printf("[OTA] Update Start: %s\n", filename.c_str());
      if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
        Update.printError(Serial);
      }
    }
    if (!Update.hasError()) {
      if (Update.write(data, len) != len) {
        Update.printError(Serial);
      }
    }
    if (final) {
      if (Update.end(true)) {
        DebugSerial.printf("[OTA] Update Success: %u Bytes\n", index + len);
      } else {
        Update.printError(Serial);
      }
    }
  });

  server.begin();
  DebugSerial.println("[HTTP] Async Web Server + WebSocket running on port 80!");

  // Allocate audio recording buffer for Whisper STT
  const size_t recordBufferBytes = MAX_RECORD_SAMPLES * sizeof(int16_t);
  if (psramFound()) {
    recordBuffer = (int16_t*)heap_caps_malloc(
      recordBufferBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  }
  if (!recordBuffer) {
    DebugSerial.println("[RECORD] PSRAM unavailable; falling back to internal heap.");
    recordBuffer = (int16_t*)heap_caps_malloc(
      recordBufferBytes, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
  }
  if (!recordBuffer) {
    DebugSerial.println("[ERROR] Failed to allocate memory for recordBuffer!");
  } else {
    DebugSerial.printf(
      "[RECORD] Allocated %u-byte Whisper buffer in %s. Free internal=%u, PSRAM=%u.\n",
      (unsigned int)recordBufferBytes,
      esp_ptr_external_ram(recordBuffer) ? "PSRAM" : "internal RAM",
      (unsigned int)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
      (unsigned int)ESP.getFreePsram());
  }

  // 1. Audio Playback Task on Core 1
  xTaskCreatePinnedToCore(
    audioTaskFunction,
    "AudioTask",
    8192,
    NULL,
    3,
    &audioTaskHandle,
    1
  );

  // 2. Decoupled Voice & Intent Task on Core 1
  xTaskCreatePinnedToCore(
    voiceTaskFunction,
    "VoiceTask",
    8192,
    NULL,
    2,
    &voiceTaskHandle,
    1
  );

  // 3. Mic Sampling & VAD Stream Task on Core 0
  xTaskCreatePinnedToCore(
    micTaskFunction,
    "MicTask",
    8192,
    NULL,
    1,
    &micTaskHandle,
    0
  );

  // 4. Non-blocking Home Assistant state synchronization on Core 1
  xTaskCreatePinnedToCore(
    haSyncTaskFunction,
    "HaSyncTask",
    6144,
    NULL,
    1,
    &haSyncTaskHandle,
    1
  );

  // 5. Dedicated streaming openWakeWord client on Core 1. It automatically
  // falls back to Whisper wake matching until WAKE_WORD_MODEL is installed.
  xTaskCreatePinnedToCore(
    wakeTaskFunction,
    "WakeTask",
    8192,
    NULL,
    2,
    &wakeTaskHandle,
    1
  );

  // Initialize Hardware BOOT Button (GPIO 0)
  pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);

  // Startup chime
  AudioCommand cmd;
  cmd.type = CMD_CHIME;
  cmd.text[0] = '\0';
  xQueueSend(audioQueue, &cmd, 0);
}

// ---------------------------------------------------------------------------
// Loop — Core 0
// ---------------------------------------------------------------------------

void loop() {
  ws.cleanupClients();

  static unsigned long lastDiagnosticPush = 0;
  static uint32_t lastPushedLogVersion = 0;
  if (ws.count() > 0 && millis() - lastDiagnosticPush >= 1000) {
    lastDiagnosticPush = millis();
    uint32_t currentLogVersion;
    portENTER_CRITICAL(&diagnosticMux);
    currentLogVersion = diagnosticLogVersion;
    portEXIT_CRITICAL(&diagnosticMux);
    const bool logsChanged = currentLogVersion != lastPushedLogVersion;
    broadcastDiagnostics(logsChanged);
    if (logsChanged) lastPushedLogVersion = currentLogVersion;
  }

  if (remoteWakeDetected) {
    remoteWakeDetected = false;
    if (assistantState == STATE_IDLE_WAIT_WAKE && triggerWordEnabled) {
      beginConfirmedWake("Hey Burden detected by streaming openWakeWord");
    }
  }

  // Reset assistant state if command listening window expires
  if (assistantState == STATE_LISTENING_FOR_COMMAND && !isRecordingVoice && !isTranscribing &&
      commandWindowExpiry > 0 &&
      (long)(millis() - commandWindowExpiry) >= 0) {
    assistantState = STATE_IDLE_WAIT_WAKE;
    commandWindowExpiry = 0;
    updateOledUI(lastOledTitle.c_str(), lastSpeechHeard.c_str(), "Act: Ready");
    broadcastStatus("idle", "Ready — Listening for 'Hey Burden'");
  }

  // Physical BOOT Button Toggle (GPIO 0)
  static bool lastBtnState = HIGH;
  static unsigned long lastBtnTime = 0;
  bool currentBtnState = digitalRead(BOOT_BUTTON_PIN);
  if (currentBtnState == LOW && lastBtnState == HIGH && (millis() - lastBtnTime > 350)) {
    lastBtnTime = millis();
    DebugSerial.println("[BUTTON] BOOT button clicked -> Toggling Govee lamps!");
    sendHomeAssistantLightCommand("toggle", "all_lamps");
    renderSmartHomeDisplay("BUTTON TOGGLE", "All Lamps", "Toggled via BOOT");
    broadcastStatus("smart_home", "Toggled lamps via BOOT button");
    AudioCommand cmd; cmd.type = CMD_CHIME; cmd.text[0] = '\0';
    xQueueSend(audioQueue, &cmd, 0);
  }
  lastBtnState = currentBtnState;

  delay(20);
}
