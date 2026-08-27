#!/usr/bin/env python3
"""Apply bounded, reviewed compatibility fixes to the pinned openWakeWord trainer."""

import argparse
from pathlib import Path


ORIGINAL = '''        X_val_fp = np.load(config["false_positive_validation_data_path"])
        X_val_fp = np.array([X_val_fp[i:i+input_shape[0]] for i in range(0, X_val_fp.shape[0]-input_shape[0], 1)])  # reshape to match model
        X_val_fp_labels = np.zeros(X_val_fp.shape[0]).astype(np.float32)
        X_val_fp = torch.utils.data.DataLoader(
            torch.utils.data.TensorDataset(torch.from_numpy(X_val_fp), torch.from_numpy(X_val_fp_labels)),
            batch_size=len(X_val_fp_labels)
        )
'''

PATCHED = '''        # Stream validation windows from the memory-mapped source. The upstream
        # list comprehension materializes tens of GiB and can stall a 32 GiB host.
        class SlidingWindowDataset(torch.utils.data.Dataset):
            def __init__(self, source_path, window_size):
                self.source = np.load(source_path, mmap_mode="r")
                self.window_size = window_size

            def __len__(self):
                return max(0, self.source.shape[0] - self.window_size)

            def __getitem__(self, index):
                window = np.array(self.source[index:index+self.window_size], copy=True)
                return torch.from_numpy(window), torch.tensor(0.0, dtype=torch.float32)

        X_val_fp = torch.utils.data.DataLoader(
            SlidingWindowDataset(config["false_positive_validation_data_path"], input_shape[0]),
            batch_size=4096,
            num_workers=0,
        )
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trainer", type=Path)
    args = parser.parse_args()
    text = args.trainer.read_text(encoding="utf-8")
    if PATCHED in text:
        print("openWakeWord streaming-validation patch already applied.")
        return 0
    if ORIGINAL not in text:
        raise RuntimeError("Pinned openWakeWord validation block changed; refusing an unsafe patch.")
    args.trainer.write_text(text.replace(ORIGINAL, PATCHED), encoding="utf-8")
    print("Applied bounded streaming validation to the pinned openWakeWord trainer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

