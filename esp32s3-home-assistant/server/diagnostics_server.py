"""Private voice diagnostics, review sync, and report-before-prune API."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import parse_qs, urlparse

LOGGER = logging.getLogger("voice_diagnostics")
DIAGNOSTICS_DIR = Path(os.environ.get("VOICE_DIAGNOSTICS_DIR", "/diagnostics"))
REPORTS_DIR = Path(os.environ.get("VOICE_REPORTS_DIR", "/reports"))
BIND_HOST = os.environ.get("VOICE_DIAGNOSTICS_HOST", "0.0.0.0")
BIND_PORT = int(os.environ.get("VOICE_DIAGNOSTICS_PORT", "10400"))
SERVE_AUDIO = os.environ.get("VOICE_DIAGNOSTICS_SERVE_AUDIO", "1").lower() in {"1", "true", "yes", "on"}
MAX_RECORDS = max(1, int(os.environ.get("VOICE_DIAGNOSTICS_MAX_RECORDS", "200")))
MAX_BYTES = max(1, int(os.environ.get("VOICE_DIAGNOSTICS_MAX_BYTES", "268435456")))
MAX_API_RECORDS = max(100_000, MAX_RECORDS)
MAINTENANCE_SECONDS = max(1.0, float(os.environ.get("VOICE_DIAGNOSTICS_MAINTENANCE_SECONDS", "4")))
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{8,120}$")
VALID_REVIEWS = {"", "correct", "wrong_stt", "wrong_action", "missed_audio"}
WRITE_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def review_path(request_id: str) -> Path:
    return REPORTS_DIR / "reviews" / f"{request_id}.json"


def load_review(request_id: str) -> dict[str, Any]:
    value = load_json(review_path(request_id), {})
    return value if isinstance(value, dict) else {}


def save_review(request_id: str, value: dict[str, Any]) -> dict[str, Any]:
    review = str(value.get("review", ""))
    if review not in VALID_REVIEWS:
        raise ValueError("invalid review")
    device_source = value.get("device_session", {})
    if not isinstance(device_source, dict):
        device_source = {}
    device_fields = (
        "id", "received_at", "wake", "heard", "reply", "matched", "result", "error", "outcome",
        "ok", "one_breath", "wake_pipeline_ms", "replay_ms", "replay_bytes", "wake_speech_ms",
        "capture_ms", "stt_ms", "action_ms", "total_ms", "pre_roll_ms", "rssi_dbm", "wake_sound",
    )
    device_session = {key: device_source.get(key) for key in device_fields if key in device_source}
    normalized = {
        "diagnostic_id": request_id,
        "review": review,
        "expected_speech": str(value.get("expected_speech", ""))[:500],
        "review_note": str(value.get("review_note", ""))[:2000],
        "device_session_id": str(value.get("device_session_id", ""))[:120],
        "device_session": device_session,
        "updated_at": utc_now(),
    }
    with WRITE_LOCK:
        atomic_json(review_path(request_id), normalized)
    return normalized


def diagnostic_paths() -> list[Path]:
    paths: list[Path] = []
    for path in DIAGNOSTICS_DIR.glob("*.json"):
        try:
            if path.is_file():
                paths.append(path)
        except OSError:
            continue
    return sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)


def record_storage(paths: list[Path] | None = None) -> tuple[int, int]:
    paths = paths if paths is not None else diagnostic_paths()
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
            wav_path = path.with_suffix(".wav")
            if wav_path.is_file():
                total += wav_path.stat().st_size
        except OSError:
            continue
    return len(paths), total


def load_records(limit: int = 50) -> list[dict[str, Any]]:
    """Load newest complete records with synchronized review annotations."""
    limit = max(1, min(MAX_API_RECORDS, limit))
    records: list[dict[str, Any]] = []
    for path in diagnostic_paths():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            request_id = str(record.get("id", "")) if isinstance(record, dict) else ""
            if not SAFE_ID.fullmatch(request_id):
                continue
            record["audio_available"] = SERVE_AUDIO and path.with_suffix(".wav").is_file()
            record["review"] = load_review(request_id)
            records.append(record)
        except (OSError, json.JSONDecodeError):
            LOGGER.warning("Ignoring unreadable diagnostic record %s", path.name)
        if len(records) >= limit:
            break
    return records


def rounded_mean(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def deterministic_findings(records: list[dict[str, Any]]) -> dict[str, Any]:
    reviews = [record.get("review", {}) for record in records]
    review_counts = Counter(str(review.get("review") or "unreviewed") for review in reviews)
    outcome_counts = Counter(str(review.get("device_session", {}).get("outcome") or "unknown") for review in reviews)
    issue_counts: Counter[str] = Counter()
    peak_values: list[float] = []
    snr_values: list[float] = []
    confusion_counts: Counter[str] = Counter()
    for record, review in zip(records, reviews):
        audio = record.get("audio", {})
        metrics = audio.get("metrics", {})
        issue_counts.update(str(issue) for issue in audio.get("issues", []))
        if isinstance(metrics.get("peak_dbfs"), (int, float)):
            peak_values.append(float(metrics["peak_dbfs"]))
        if isinstance(metrics.get("estimated_snr_db"), (int, float)):
            snr_values.append(float(metrics["estimated_snr_db"]))
        if review.get("review") == "wrong_stt" and review.get("expected_speech"):
            heard = str(record.get("decoder", {}).get("final_text") or "no transcript")
            confusion_counts[f"{review['expected_speech']} -> {heard}"] += 1

    count = len(records)
    reviewed = count - review_counts.get("unreviewed", 0)
    wrong_stt = review_counts.get("wrong_stt", 0)
    recommendations: list[str] = []
    if not reviewed:
        recommendations.append("Review and label sessions before using this batch for tuning decisions.")
    elif reviewed < count:
        recommendations.append(f"Label the remaining {count - reviewed} sessions to reduce selection bias.")
    if reviewed and wrong_stt / reviewed >= 0.1:
        recommendations.append("Recognition errors exceed 10% of reviewed sessions; inspect the confusion pairs and N-best margins.")
    if issue_counts.get("LOW_ESTIMATED_SNR", 0):
        recommendations.append("Low-SNR captures exist; compare their error rate before changing grammar or microphone processing.")
    if issue_counts.get("POSSIBLE_END_TRUNCATION", 0):
        recommendations.append("Possible ending truncation exists; compare tail activity with missed off/on tokens and VAD timing.")
    if issue_counts.get("CLIPPING", 0):
        recommendations.append("Clipped captures exist; reduce microphone gain before decoder or grammar tuning.")
    if not recommendations:
        recommendations.append("No deterministic warning threshold was crossed; preserve this batch as a baseline.")
    return {
        "session_count": count,
        "reviewed_count": reviewed,
        "review_coverage_percent": round((reviewed * 100 / count), 1) if count else 0.0,
        "review_counts": dict(sorted(review_counts.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "acoustic_issue_counts": dict(sorted(issue_counts.items())),
        "mean_peak_dbfs": rounded_mean(peak_values),
        "mean_estimated_snr_db": rounded_mean(snr_values),
        "confusion_pairs": [{"pair": pair, "count": total} for pair, total in sorted(confusion_counts.items())],
        "recommendations": recommendations,
    }


def build_report(records: list[dict[str, Any]], storage_bytes: int) -> dict[str, Any]:
    canonical_records = json.dumps(records, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical_records).hexdigest()
    ordered = sorted(records, key=lambda record: str(record.get("started_at", "")))
    return {
        "schema_version": 1,
        "report_id": f"research-{digest[:16]}",
        "created_at": utc_now(),
        "trigger": {"record_limit": MAX_RECORDS, "storage_limit_bytes": MAX_BYTES, "captured_storage_bytes": storage_bytes},
        "range": {
            "first_started_at": ordered[0].get("started_at") if ordered else None,
            "last_completed_at": ordered[-1].get("completed_at") if ordered else None,
        },
        "source_sha256": digest,
        "findings": deterministic_findings(ordered),
        "records": ordered,
    }


def list_reports() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(REPORTS_DIR.glob("research-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        report = load_json(path, {})
        if not isinstance(report, dict) or not SAFE_ID.fullmatch(str(report.get("report_id", ""))):
            continue
        analysis = load_json(REPORTS_DIR / "analysis" / f"{report['report_id']}.json", {})
        findings = report.get("findings", {})
        reports.append({
            "report_id": report["report_id"],
            "created_at": report.get("created_at"),
            "range": report.get("range", {}),
            "session_count": findings.get("session_count", 0),
            "reviewed_count": findings.get("reviewed_count", 0),
            "review_coverage_percent": findings.get("review_coverage_percent", 0),
            "review_counts": findings.get("review_counts", {}),
            "acoustic_issue_counts": findings.get("acoustic_issue_counts", {}),
            "recommendations": findings.get("recommendations", []),
            "analysis": analysis if isinstance(analysis, dict) else {},
        })
    return reports


def research_status() -> dict[str, Any]:
    paths = diagnostic_paths()
    count, used_bytes = record_storage(paths)
    reports = list_reports()
    analyzed = sum(1 for report in reports if report.get("analysis", {}).get("status") == "analyzed")
    return {
        "raw_records": count,
        "raw_bytes": used_bytes,
        "record_limit": MAX_RECORDS,
        "storage_limit_bytes": MAX_BYTES,
        "record_percent": round(count * 100 / MAX_RECORDS, 1),
        "storage_percent": round(used_bytes * 100 / MAX_BYTES, 1),
        "reports": len(reports),
        "analyzed_reports": analyzed,
        "pending_reports": len(reports) - analyzed,
    }


def report_before_prune() -> str | None:
    """Create one complete immutable batch report, then remove covered raw files."""
    with WRITE_LOCK:
        # Hold the same lock used by review updates so the report cannot miss a
        # label or note that completes while the rollover snapshot is built.
        paths = diagnostic_paths()
        count, used_bytes = record_storage(paths)
        if count <= MAX_RECORDS and used_bytes <= MAX_BYTES:
            return None
        records = load_records(MAX_API_RECORDS)
        if len(records) != count:
            LOGGER.error("Retention paused: loaded %s of %s diagnostic records", len(records), count)
            return None
        report = build_report(records, used_bytes)
        report_path = REPORTS_DIR / f"{report['report_id']}.json"
        if not report_path.exists():
            atomic_json(report_path, report)
        for path in paths:
            request_id = path.stem
            path.unlink(missing_ok=True)
            path.with_suffix(".wav").unlink(missing_ok=True)
            review_path(request_id).unlink(missing_ok=True)
    LOGGER.info("RESEARCH_REPORT %s captured %s sessions before raw-data rollover", report["report_id"], count)
    return str(report["report_id"])


def maintenance_loop() -> None:
    while True:
        try:
            report_before_prune()
        except Exception:
            LOGGER.exception("Research retention maintenance failed; raw diagnostics were retained")
        time.sleep(MAINTENANCE_SECONDS)


class DiagnosticHandler(BaseHTTPRequestHandler):
    """Serve diagnostic evidence and accept bounded local research metadata."""

    server_version = "VoiceDiagnostics/2"

    def _headers(self, status: HTTPStatus, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def _json(self, status: HTTPStatus, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 16_384:
            raise ValueError("invalid request size")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._headers(HTTPStatus.NO_CONTENT, "text/plain", 0)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/review"):
                request_id = parsed.path.removeprefix("/api/sessions/").removesuffix("/review")
                if not SAFE_ID.fullmatch(request_id):
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid diagnostic id"})
                    return
                if not (DIAGNOSTICS_DIR / f"{request_id}.json").is_file():
                    self._json(HTTPStatus.NOT_FOUND, {"error": "diagnostic not found"})
                    return
                self._json(HTTPStatus.OK, {"review": save_review(request_id, self._body())})
                return
            if parsed.path.startswith("/api/reports/") and parsed.path.endswith("/analysis"):
                report_id = parsed.path.removeprefix("/api/reports/").removesuffix("/analysis")
                if not SAFE_ID.fullmatch(report_id) or not (REPORTS_DIR / f"{report_id}.json").is_file():
                    self._json(HTTPStatus.NOT_FOUND, {"error": "report not found"})
                    return
                body = self._body()
                status = str(body.get("status", "pending"))
                if status not in {"pending", "analyzed"}:
                    raise ValueError("invalid analysis status")
                analysis = {
                    "report_id": report_id,
                    "status": status,
                    "summary": str(body.get("summary", ""))[:4000],
                    "analyzed_at": utc_now() if status == "analyzed" else None,
                }
                with WRITE_LOCK:
                    atomic_json(REPORTS_DIR / "analysis" / f"{report_id}.json", analysis)
                self._json(HTTPStatus.OK, {"analysis": analysis})
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", **research_status()})
            return
        if parsed.path == "/api/research/status":
            self._json(HTTPStatus.OK, {"schema_version": 1, **research_status()})
            return
        if parsed.path == "/api/reports":
            self._json(HTTPStatus.OK, {"schema_version": 1, "reports": list_reports()})
            return
        if parsed.path.startswith("/api/reports/"):
            report_id = parsed.path.removeprefix("/api/reports/")
            if not SAFE_ID.fullmatch(report_id):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid report id"})
                return
            report = load_json(REPORTS_DIR / f"{report_id}.json", None)
            if report is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "report not found"})
                return
            report["analysis"] = load_json(REPORTS_DIR / "analysis" / f"{report_id}.json", {})
            self._json(HTTPStatus.OK, report)
            return
        if parsed.path == "/api/sessions":
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
            except ValueError:
                limit = 50
            self._json(HTTPStatus.OK, {"schema_version": 2, "sessions": load_records(limit), "research": research_status()})
            return
        if parsed.path.startswith("/api/sessions/"):
            request_id = parsed.path.removeprefix("/api/sessions/")
            if not SAFE_ID.fullmatch(request_id):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid diagnostic id"})
                return
            record = load_json(DIAGNOSTICS_DIR / f"{request_id}.json", None)
            if record is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "diagnostic not found"})
                return
            record["audio_available"] = SERVE_AUDIO and (DIAGNOSTICS_DIR / f"{request_id}.wav").is_file()
            record["review"] = load_review(request_id)
            self._json(HTTPStatus.OK, record)
            return
        if parsed.path.startswith("/audio/") and parsed.path.endswith(".wav"):
            if not SERVE_AUDIO:
                self._json(HTTPStatus.FORBIDDEN, {"error": "audio serving disabled"})
                return
            request_id = parsed.path.removeprefix("/audio/").removesuffix(".wav")
            if not SAFE_ID.fullmatch(request_id):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid diagnostic id"})
                return
            try:
                body = (DIAGNOSTICS_DIR / f"{request_id}.wav").read_bytes()
            except FileNotFoundError:
                self._json(HTTPStatus.NOT_FOUND, {"error": "audio not found"})
                return
            self._headers(HTTPStatus.OK, "audio/wav", len(body))
            self.wfile.write(body)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, message: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.client_address[0], message % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=maintenance_loop, name="research-retention", daemon=True).start()
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), DiagnosticHandler)
    LOGGER.info("Serving voice diagnostics on %s:%s; research reports in %s", BIND_HOST, BIND_PORT, REPORTS_DIR)
    server.serve_forever()


if __name__ == "__main__":
    main()
