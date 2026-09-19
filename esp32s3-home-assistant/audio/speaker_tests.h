#pragma once
#include "speaker_samples.h"
#include "esphome/components/speaker/speaker.h"
#include "esphome/components/audio/audio.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "esphome/core/helpers.h"
#include <cmath>
#include <vector>

namespace speaker_tests {
static bool active = false, draining = false;
static uint32_t started = 0;
static size_t cursor = 0;
static std::vector<int16_t, esphome::RAMAllocator<int16_t>> pcm;
static int channels = 1;
static const char *names[] = {"Sweep", "Chime", "Random melody", "Soft noise", "Speech A mono", "Speech B mono", "Speech A stereo", "Level steps"};

inline void stop(esphome::speaker::Speaker *speaker) {
  if (active) speaker->stop();
  active = false;
  pcm.clear();
}

inline void start(esphome::speaker::Speaker *speaker, int kind) {
  if (active || kind < 0 || kind > 7) return;
  channels = kind == 6 ? 2 : 1;
  pcm.clear();
  if (kind >= 4 && kind <= 6) {
    const int16_t *source = kind == 5 ? speaker_samples::speech_1 : speaker_samples::speech_0;
    const size_t count = kind == 5 ? sizeof(speaker_samples::speech_1)/2 : sizeof(speaker_samples::speech_0)/2;
    pcm.reserve(count * channels);
    for (size_t i = 0; i < count; ++i) {
      pcm.push_back(source[i]);
      if (channels == 2) pcm.push_back(source[i]);
    }
  } else {
    const size_t count = kind == 7 ? 64000 : 32000;
    pcm.reserve(count);
    float phase = 0, noise = 0;
    uint32_t rng = esphome::millis() | 1;
    float notes[8];
    const float scale[] = {523.25f, 587.33f, 659.25f, 783.99f, 880.0f, 1046.5f};
    for (auto &note : notes) { rng = rng * 1664525u + 1013904223u; note = scale[(rng >> 16) % 6]; }
    for (size_t i = 0; i < count; ++i) {
      const float t = i / 16000.0f;
      float frequency = 1000, amplitude = 0.50f, envelope = 1;
      if (kind == 0) frequency = 250 * powf(16.0f, t / 2);
      if (kind == 1) { frequency = t < 0.65f ? 659.25f : 523.25f; envelope = expf(-4 * fmodf(t, 0.65f)); }
      if (kind == 2) { frequency = notes[(i / 4000) % 8]; envelope = fminf(1, (i % 4000) / 160.0f) * fminf(1, (3999 - i % 4000) / 320.0f); }
      if (kind == 7) {
        const float levels[] = {0.10f, 0.25f, 0.50f, 0.80f};
        amplitude = levels[i / 16000];
        const size_t within = i % 16000;
        envelope = within < 12000 ? fminf(1, within / 320.0f) * fminf(1, (12000 - within) / 320.0f) : 0;
      }
      phase += 6.283185307f * frequency / 16000;
      if (phase > 6.283185307f) phase -= 6.283185307f;
      float value = sinf(phase);
      if (kind == 3) {
        rng = rng * 1664525u + 1013904223u;
        noise = 0.75f * noise + 0.25f * ((rng >> 16) / 32768.0f - 1);
        value = noise; amplitude = 0.5f;
      }
      envelope *= fminf(1, i / 320.0f) * fminf(1, (count - 1 - i) / 320.0f);
      pcm.push_back(static_cast<int16_t>(32767 * amplitude * envelope * value));
    }
  }
  cursor = 0; draining = false; active = true; started = esphome::millis();
  speaker->set_audio_stream_info(esphome::audio::AudioStreamInfo(16, channels, 16000));
  speaker->start();
  ESP_LOGI("speaker_tests", "%s: %u frames, channels=%d, control=%.3f", names[kind], (unsigned)(pcm.size()/channels), channels, speaker->get_volume());
}

// Feed at most 20 ms each tick, retain unaccepted bytes, and never block the
// main loop waiting for room. End only after hardware drains the final frame.
inline void tick(esphome::speaker::Speaker *speaker) {
  if (!active) return;
  if (esphome::millis() - started > 15000) {
    ESP_LOGE("speaker_tests", "Playback timed out at %u/%u bytes", (unsigned)cursor, (unsigned)(pcm.size()*2));
    stop(speaker); return;
  }
  if (draining) {
    if (speaker->is_stopped()) {
      ESP_LOGI("speaker_tests", "Complete: %u/%u bytes", (unsigned)cursor, (unsigned)(pcm.size()*2));
      active = false; pcm.clear();
    }
    return;
  }
  if (!speaker->is_running()) return;
  const size_t remaining = pcm.size()*2 - cursor;
  const size_t bytes = std::min(remaining, static_cast<size_t>(640 * channels));
  cursor += speaker->play(reinterpret_cast<const uint8_t *>(pcm.data()) + cursor, bytes, 0);
  if (cursor == pcm.size()*2) { speaker->finish(); draining = true; }
}
}
