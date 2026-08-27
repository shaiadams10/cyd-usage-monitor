#include "buffered_microphone.h"

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

#include <algorithm>
#include <cstring>

namespace esphome::buffered_microphone {

static const char *const TAG = "buffered_microphone";

void BufferedMicrophone::setup() {
  if (this->source_ == nullptr) {
    ESP_LOGE(TAG, "Source microphone is not configured");
    this->mark_failed();
    return;
  }

  this->audio_stream_info_ = this->source_->get_audio_stream_info();
  this->history_size_ = this->audio_stream_info_.ms_to_bytes(this->history_duration_ms_);
  const size_t bytes_per_frame = this->audio_stream_info_.frames_to_bytes(1);
  this->history_size_ = (this->history_size_ / bytes_per_frame) * bytes_per_frame;

  RAMAllocator<uint8_t> allocator(RAMAllocator<uint8_t>::ALLOC_EXTERNAL);
  this->history_ = allocator.allocate(this->history_size_);
  if (this->history_ == nullptr) {
    ESP_LOGE(TAG, "Could not allocate %u-byte PSRAM history", (unsigned) this->history_size_);
    this->mark_failed();
    return;
  }
  memset(this->history_, 0, this->history_size_);

  this->mutex_ = xSemaphoreCreateMutex();
  if (this->mutex_ == nullptr) {
    ESP_LOGE(TAG, "Could not allocate history mutex");
    this->mark_failed();
    return;
  }

  // This callback remains registered while the proxy is stopped. The physical
  // microphone is kept running by microWakeWord, so command pre-roll continues
  // to accumulate without making Voice Assistant an active listener.
  this->source_->add_data_callback(
      [this](const std::vector<uint8_t> &data) { this->handle_source_data_(data); });
  this->state_ = microphone::STATE_STOPPED;
}

void BufferedMicrophone::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Buffered Microphone:\n"
                "  History: %u ms (%u bytes, PSRAM)\n"
                "  Pre-roll before wake marker: %u ms",
                (unsigned) this->history_duration_ms_, (unsigned) this->history_size_,
                (unsigned) this->pre_roll_duration_ms_);
}

void BufferedMicrophone::mark_wake_detected() {
  if (this->is_failed() || this->mutex_ == nullptr)
    return;

  xSemaphoreTake(this->mutex_, portMAX_DELAY);
  this->wake_marker_sequence_ = this->total_bytes_received_;
  this->wake_marker_ms_ = millis();
  this->wake_marker_valid_ = true;
  xSemaphoreGive(this->mutex_);

  ESP_LOGI(TAG, "Wake marker captured at source byte %llu", (unsigned long long) this->wake_marker_sequence_);
}

void BufferedMicrophone::start() {
  if (this->is_failed() || this->source_ == nullptr || this->state_ == microphone::STATE_RUNNING)
    return;

  // Acquire a physical-microphone listener before microWakeWord releases its
  // listener, preserving continuous I2S capture across the handoff.
  this->state_ = microphone::STATE_STARTING;
  this->source_->start();

  std::vector<uint8_t> replay;
  xSemaphoreTake(this->mutex_, portMAX_DELAY);

  if (this->wake_marker_valid_) {
    const uint64_t oldest_available =
        this->total_bytes_received_ > this->history_size_ ? this->total_bytes_received_ - this->history_size_ : 0;
    const uint64_t requested_pre_roll = this->audio_stream_info_.ms_to_bytes(this->pre_roll_duration_ms_);
    uint64_t replay_start = this->wake_marker_sequence_ > requested_pre_roll
                                ? this->wake_marker_sequence_ - requested_pre_roll
                                : 0;
    replay_start = std::max(replay_start, oldest_available);
    this->copy_history_range_(replay_start, this->total_bytes_received_, replay);
  }

  this->state_ = microphone::STATE_RUNNING;
  this->last_replay_bytes_ = replay.size();
  this->last_replay_duration_ms_ = this->audio_stream_info_.bytes_to_ms(replay.size());

  // Holding the mutex prevents a live source callback from interleaving with
  // the historical frames. Once replay returns, the blocked complete source
  // chunk is forwarded next, with no duplicate or gap at the boundary.
  if (!replay.empty())
    this->data_callbacks_.call(replay);

  const uint32_t wake_to_start_ms = this->wake_marker_valid_ ? millis() - this->wake_marker_ms_ : 0;
  this->wake_marker_valid_ = false;
  xSemaphoreGive(this->mutex_);

  ESP_LOGI(TAG, "Voice capture started | replay=%u bytes/%u ms | wake_to_start=%u ms",
           (unsigned) this->last_replay_bytes_, (unsigned) this->last_replay_duration_ms_,
           (unsigned) wake_to_start_ms);
}

void BufferedMicrophone::stop() {
  if (this->state_ == microphone::STATE_STOPPED || this->source_ == nullptr)
    return;

  xSemaphoreTake(this->mutex_, portMAX_DELAY);
  this->state_ = microphone::STATE_STOPPED;
  this->wake_marker_valid_ = false;
  xSemaphoreGive(this->mutex_);
  this->source_->stop();
}

void BufferedMicrophone::handle_source_data_(const std::vector<uint8_t> &data) {
  if (this->is_failed() || data.empty() || this->mutex_ == nullptr)
    return;

  xSemaphoreTake(this->mutex_, portMAX_DELAY);
  this->write_history_(data.data(), data.size());
  if (this->state_ == microphone::STATE_RUNNING)
    this->data_callbacks_.call(data);
  xSemaphoreGive(this->mutex_);
}

void BufferedMicrophone::write_history_(const uint8_t *data, size_t length) {
  if (length >= this->history_size_) {
    data += length - this->history_size_;
    length = this->history_size_;
  }

  size_t write_index = static_cast<size_t>(this->total_bytes_received_ % this->history_size_);
  const size_t first = std::min(length, this->history_size_ - write_index);
  memcpy(this->history_ + write_index, data, first);
  if (length > first)
    memcpy(this->history_, data + first, length - first);
  this->total_bytes_received_ += length;
}

void BufferedMicrophone::copy_history_range_(uint64_t start_sequence, uint64_t end_sequence,
                                             std::vector<uint8_t> &output) {
  if (end_sequence <= start_sequence)
    return;

  const size_t length = static_cast<size_t>(end_sequence - start_sequence);
  output.resize(length);
  const size_t read_index = static_cast<size_t>(start_sequence % this->history_size_);
  const size_t first = std::min(length, this->history_size_ - read_index);
  memcpy(output.data(), this->history_ + read_index, first);
  if (length > first)
    memcpy(output.data() + first, this->history_, length - first);
}

}  // namespace esphome::buffered_microphone

