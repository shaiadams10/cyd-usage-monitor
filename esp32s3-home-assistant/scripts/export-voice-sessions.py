#!/usr/bin/env python3
"""Export ESP32 voice sessions from a Home Assistant Recorder SQLite database.

The firmware publishes a unique Current Voice Session value before clearing and
updating the per-session entities. This tool packages those state transitions
for offline accuracy/latency research without retaining raw microphone audio.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any


FIELD_SUFFIXES = {
    "wake": "last_wake_word",
    "heard": "heard_exact_stt",
    "reply": "assistant_reply_exact",
    "matched": "matched_command",
    "result": "action_result",
    "outcome": "intent_routing_outcome",
    "timing": "last_pipeline_timing",
    "error": "last_error",
    "wake_pipeline_ms": "wake_to_pipeline",
    "replay_ms": "replayed_command_audio",
    "replay_bytes": "replayed_command_bytes",
    "wake_speech_ms": "wake_to_speech_detection",
    "capture_ms": "speech_capture_duration",
    "stt_ms": "stt_processing",
    "action_ms": "wake_to_action",
    "total_ms": "total_busy_time",
}


def load_rows(connection: sqlite3.Connection) -> list[tuple[str, str, float]]:
    query = """
        SELECT sm.entity_id, s.state, s.last_updated_ts
        FROM states AS s
        JOIN states_meta AS sm ON sm.metadata_id = s.metadata_id
        WHERE sm.entity_id LIKE '%esp32_s3_home_assistant%'
          AND s.last_updated_ts IS NOT NULL
        ORDER BY s.last_updated_ts ASC
    """
    return list(connection.execute(query))


def package_sessions(rows: list[tuple[str, str, float]], limit: int) -> list[dict[str, Any]]:
    starts = [
        (index, state, timestamp)
        for index, (entity_id, state, timestamp) in enumerate(rows)
        if entity_id.endswith("current_voice_session") and state not in {"", "unknown", "unavailable"}
    ]
    sessions: list[dict[str, Any]] = []
    for position, (start_index, session_id, started_at) in enumerate(starts):
        end_index = starts[position + 1][0] if position + 1 < len(starts) else len(rows)
        record: dict[str, Any] = {
            "id": session_id,
            "started_at_epoch": started_at,
        }
        for entity_id, state, _timestamp in rows[start_index:end_index]:
            for field, suffix in FIELD_SUFFIXES.items():
                if entity_id.endswith(suffix):
                    record[field] = state
                    break
        sessions.append(record)
    return sessions[-limit:]


def write_output(records: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".csv":
        fields = ["id", "started_at_epoch", *FIELD_SUFFIXES]
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return
    output.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="Path to home-assistant_v2.db")
    parser.add_argument("--output", required=True, type=Path, help="Destination .json or .csv file")
    parser.add_argument("--limit", type=int, default=500, help="Newest sessions to export (default: 500)")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    with sqlite3.connect(f"file:{args.db}?mode=ro", uri=True) as connection:
        records = package_sessions(load_rows(connection), args.limit)
    write_output(records, args.output)
    print(f"Exported {len(records)} voice sessions to {args.output}")


if __name__ == "__main__":
    main()
