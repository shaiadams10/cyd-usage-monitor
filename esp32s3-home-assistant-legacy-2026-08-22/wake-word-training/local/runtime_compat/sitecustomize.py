"""Small compatibility shims for modern PyTorch with openWakeWord training."""

from types import SimpleNamespace

import soundfile
import torchaudio


if not hasattr(torchaudio, "info"):
    def _audio_info(path):
        metadata = soundfile.info(path)
        return SimpleNamespace(
            num_frames=metadata.frames,
            sample_rate=metadata.samplerate,
            num_channels=metadata.channels,
        )

    torchaudio.info = _audio_info

