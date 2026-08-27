# Real-device validation recordings

Store private validation audio here only temporarily; audio files are ignored by
Git. Use 16 kHz, mono, signed 16-bit PCM WAV whenever possible.

For the first acceptance pass, capture:

- 10–20 natural `Hey Burden` attempts through the ESP32's INMP441 microphone;
- attempts from near, normal, and far listening positions;
- quiet-room and normal TV/fan/background-noise conditions;
- at least 20 ordinary-speech clips, including every negative phrase in
  `../training-profile.json`.

Do not use these few personal samples as the only base training data. They are
most valuable for measuring misses and false wakes and selecting the operating
threshold. Never commit voice recordings.
