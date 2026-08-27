"""Tests for voice diagnostics research retention and API readers."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import diagnostics_server


class DiagnosticsServerTests(unittest.TestCase):
    def test_load_records_is_newest_first_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            first = directory / "20260823T120000000Z-aaaaaaaa.json"
            second = directory / "20260823T120001000Z-bbbbbbbb.json"
            first.write_text(json.dumps({"id": first.stem}), encoding="utf-8")
            second.write_text(json.dumps({"id": second.stem}), encoding="utf-8")
            os.utime(first, (1000, 1000))
            os.utime(second, (1001, 1001))
            with patch.object(diagnostics_server, "DIAGNOSTICS_DIR", directory):
                records = diagnostics_server.load_records(1)
            self.assertEqual([second.stem], [record["id"] for record in records])

    def test_load_records_ignores_malformed_and_unsafe_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            (directory / "broken.json").write_text("{", encoding="utf-8")
            (directory / "unsafe.json").write_text(json.dumps({"id": "../unsafe"}), encoding="utf-8")
            with patch.object(diagnostics_server, "DIAGNOSTICS_DIR", directory):
                self.assertEqual([], diagnostics_server.load_records())

    def test_pressure_creates_report_before_removing_covered_raw_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            diagnostics = root / "diagnostics"
            reports = root / "reports"
            diagnostics.mkdir()
            ids = ["20260823T120000000Z-aaaaaaaa", "20260823T120001000Z-bbbbbbbb"]
            for index, request_id in enumerate(ids):
                record = {
                    "id": request_id,
                    "started_at": f"2026-08-23T12:00:0{index}.000Z",
                    "completed_at": f"2026-08-23T12:00:0{index}.500Z",
                    "audio": {"issues": ["LOW_ESTIMATED_SNR"], "metrics": {"estimated_snr_db": 5.0}},
                    "decoder": {"final_text": "turn on the lights"},
                }
                (diagnostics / f"{request_id}.json").write_text(json.dumps(record), encoding="utf-8")
                (diagnostics / f"{request_id}.wav").write_bytes(b"RIFFaudio")

            with (
                patch.object(diagnostics_server, "DIAGNOSTICS_DIR", diagnostics),
                patch.object(diagnostics_server, "REPORTS_DIR", reports),
                patch.object(diagnostics_server, "MAX_RECORDS", 1),
                patch.object(diagnostics_server, "MAX_BYTES", 1_000_000),
            ):
                diagnostics_server.save_review(ids[0], {
                    "review": "wrong_stt",
                    "expected_speech": "turn off the lights",
                    "review_note": "Polarity was reversed",
                    "device_session": {"outcome": "CUSTOM ACTION SUCCEEDED"},
                })
                report_id = diagnostics_server.report_before_prune()
                self.assertIsNotNone(report_id)
                self.assertEqual([], list(diagnostics.glob("*.json")))
                self.assertEqual([], list(diagnostics.glob("*.wav")))
                report = json.loads((reports / f"{report_id}.json").read_text(encoding="utf-8"))
                self.assertEqual(2, report["findings"]["session_count"])
                self.assertEqual(1, report["findings"]["reviewed_count"])
                self.assertEqual("wrong_stt", report["records"][0]["review"]["review"])
                self.assertEqual(
                    "turn off the lights -> turn on the lights",
                    report["findings"]["confusion_pairs"][0]["pair"],
                )

    def test_no_time_based_retention(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            diagnostics = root / "diagnostics"
            reports = root / "reports"
            diagnostics.mkdir()
            request_id = "20200101T000000000Z-aaaaaaaa"
            path = diagnostics / f"{request_id}.json"
            path.write_text(json.dumps({"id": request_id}), encoding="utf-8")
            os.utime(path, (1, 1))
            with (
                patch.object(diagnostics_server, "DIAGNOSTICS_DIR", diagnostics),
                patch.object(diagnostics_server, "REPORTS_DIR", reports),
                patch.object(diagnostics_server, "MAX_RECORDS", 200),
                patch.object(diagnostics_server, "MAX_BYTES", 1_000_000),
            ):
                self.assertIsNone(diagnostics_server.report_before_prune())
                self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
