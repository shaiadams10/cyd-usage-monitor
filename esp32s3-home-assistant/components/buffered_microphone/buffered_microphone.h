#pragma once

#include "esphome/components/microphone/microphone.h"
#include "esphome/core/component.h"
#include "esphome/core/helpers.h"

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include <cstddef>
#include <cstdint>
#include <vector>

namespace esphome::buffered_microphone {

class BufferedMicrophone final : public microphone::Microphone, public Component {
 public:
  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA - 1.0f; }

  void start() override;
  void stop() override;

  void set_source(microphone::Microphone *source) { this->source_ = source; }
  void set_history_duration_ms(uint32_t duration_ms) { this->history_duration_ms_ = duration_ms; }
  void set_pre_roll_duration_ms(uint32_t duration_ms) { this->pre_roll_duration_ms_ = duration_ms; }

  // Called at the exact local-wake callback, before voice_assistant.start.
  // The next start() replays pre_roll_duration before this marker plus every
  // complete source chunk received between the marker and start().
  void mark_wake_detected();

  uint32_t get_last_replay_duration_ms() const { return this->last_replay_duration_ms_; }
  size_t get_last_replay_bytes() const { return this->last_replay_bytes_; }

 protected:
  void handle_source_data_(const std::vector<uint8_t> &data);
  void write_history_(const uint8_t *data, size_t length);
  void copy_history_range_(uint64_t start_sequence, uint64_t end_sequence, std::vector<uint8_t> &output);

  microphone::Microphone *source_{nullptr};
  SemaphoreHandle_t mutex_{nullptr};
  uint8_t *history_{nullptr};
  size_t history_size_{0};
  uint64_t total_bytes_received_{0};

  uint32_t history_duration_ms_{1000};
  uint32_t pre_roll_duration_ms_{260};

  bool wake_marker_valid_{false};
  uint64_t wake_marker_sequence_{0};
  uint32_t wake_marker_ms_{0};

  uint32_t last_replay_duration_ms_{0};
  size_t last_replay_bytes_{0};
};

}  // namespace esphome::buffered_microphone

