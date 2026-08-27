"""Kaldi transcription with bounded, local acoustic diagnostics.

This is a minimally instrumented copy of Speech-to-Phrase 1.4.3's
``transcribe_kaldi.py``. It preserves the recognizer's decoder and fuzzy
matching behavior while retaining the information that the Wyoming transcript
response cannot carry.
"""

import array
import asyncio
import io
import json
import logging
import math
import os
import shlex
import tempfile
import uuid
import wave
from collections.abc import AsyncIterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .const import CHANNELS, EPS, RATE, WIDTH, Settings
from .hassil_fst import Fst, decode_meta
from .models import Model
from .speech_tools import SpeechTools

_LOGGER = logging.getLogger(__name__)

MAX_ACTIVE = 7000
LATTICE_BEAM = 8.0
DECODE_ACOUSTIC_SCALE = 1.0
BEAM = 24.0
NBEST_ACOUSTIC_SCALE = 0.9
NBEST = 3
NBEST_PENALTY = 0.1
MAX_FUZZY_COST = 2.0

DIAGNOSTICS_DIR = os.environ.get("STP_DIAGNOSTICS_DIR", "")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _dbfs(value: float) -> Optional[float]:
    if value <= 0:
        return None
    return round(20.0 * math.log10(value / 32768.0), 2)


def _rms(samples: List[int]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def _audio_metrics(audio: bytes) -> Dict[str, object]:
    pcm = array.array("h")
    pcm.frombytes(audio[: len(audio) - (len(audio) % WIDTH)])
    samples = list(pcm)
    if not samples:
        return {
            "sample_count": 0,
            "duration_ms": 0,
            "peak_dbfs": None,
            "rms_dbfs": None,
            "clipping_percent": 0.0,
            "dc_offset": 0.0,
            "estimated_noise_dbfs": None,
            "estimated_snr_db": None,
            "leading_silence_ms": 0,
            "trailing_silence_ms": 0,
            "tail_active": False,
        }

    peak = max(abs(sample) for sample in samples)
    rms = _rms(samples)
    clipping = sum(1 for sample in samples if abs(sample) >= 32760)
    dc_offset = sum(samples) / len(samples)

    frame_samples = max(1, RATE // 50)  # 20 ms
    frame_rms = [_rms(samples[index : index + frame_samples]) for index in range(0, len(samples), frame_samples)]
    sorted_frames = sorted(frame_rms)
    noise_rms = sorted_frames[min(len(sorted_frames) - 1, max(0, len(sorted_frames) // 10))]
    silence_threshold = max(184.0, noise_rms * 2.5)  # at least -45 dBFS

    leading_frames = 0
    for value in frame_rms:
        if value > silence_threshold:
            break
        leading_frames += 1

    trailing_frames = 0
    for value in reversed(frame_rms):
        if value > silence_threshold:
            break
        trailing_frames += 1

    tail_samples = samples[-max(1, int(RATE * 0.15)) :]
    tail_rms = _rms(tail_samples)
    tail_dbfs = _dbfs(tail_rms)
    noise_dbfs = _dbfs(noise_rms)
    snr = None
    if noise_rms > 0 and rms > 0:
        snr = round(20.0 * math.log10(rms / noise_rms), 2)

    return {
        "sample_count": len(samples),
        "duration_ms": round(len(samples) * 1000 / RATE),
        "peak_dbfs": _dbfs(float(peak)),
        "rms_dbfs": _dbfs(rms),
        "clipping_percent": round(clipping * 100.0 / len(samples), 4),
        "dc_offset": round(dc_offset, 2),
        "estimated_noise_dbfs": noise_dbfs,
        "estimated_snr_db": snr,
        "leading_silence_ms": leading_frames * 20,
        "trailing_silence_ms": trailing_frames * 20,
        "tail_rms_dbfs": tail_dbfs,
        "tail_active": bool(tail_dbfs is not None and tail_dbfs > -35.0 and trailing_frames == 0),
    }


def _parse_cost_archive(path: Path) -> Dict[str, float]:
    costs: Dict[str, float] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                costs[parts[0]] = float(parts[-1])
    except (OSError, ValueError):
        _LOGGER.exception("Unable to parse Kaldi cost archive: %s", path)
    return costs


def _parse_candidates(symbol_text: str, language_costs: Dict[str, float], acoustic_costs: Dict[str, float]) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    for line in symbol_text.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        key = parts[0]
        raw_text = " ".join(parts[1:])
        try:
            text = decode_meta(raw_text)
        except Exception:  # diagnostics must never break recognition
            text = raw_text
        language_cost = language_costs.get(key)
        scaled_acoustic_cost = acoustic_costs.get(key)
        total_cost = None
        if language_cost is not None and scaled_acoustic_cost is not None:
            total_cost = language_cost + scaled_acoustic_cost
        candidates.append(
            {
                "rank": len(candidates) + 1,
                "key": key,
                "text": text,
                "raw_text": raw_text,
                "language_cost": round(language_cost, 4) if language_cost is not None else None,
                "scaled_acoustic_cost": round(scaled_acoustic_cost, 4) if scaled_acoustic_cost is not None else None,
                "acoustic_cost": round(scaled_acoustic_cost / NBEST_ACOUSTIC_SCALE, 4) if scaled_acoustic_cost is not None else None,
                "total_cost": round(total_cost, 4) if total_cost is not None else None,
            }
        )
    return candidates


def _parse_ctm(symbol_text: str) -> List[Dict[str, object]]:
    words: List[Dict[str, object]] = []
    for line in symbol_text.splitlines():
        parts = line.strip().split()
        if len(parts) < 6:
            continue
        try:
            words.append(
                {
                    "word": parts[4],
                    "start_ms": round(float(parts[2]) * 1000),
                    "duration_ms": round(float(parts[3]) * 1000),
                    "confidence": round(float(parts[5]), 4),
                }
            )
        except ValueError:
            continue
    return words


def _parse_candidate_ctm(symbol_text: str) -> Dict[str, List[Dict[str, object]]]:
    candidates: Dict[str, List[Dict[str, object]]] = {}
    for line in symbol_text.splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            candidates.setdefault(parts[0], []).append(
                {
                    "word": parts[4],
                    "start_ms": round(float(parts[2]) * 1000),
                    "duration_ms": round(float(parts[3]) * 1000),
                    "confidence": None,
                }
            )
        except ValueError:
            continue
    return candidates


def _write_diagnostic(request_id: str, started_at: str, model: Model, audio: bytes, decoder: Dict[str, object]) -> None:
    if not DIAGNOSTICS_DIR:
        return
    try:
        directory = Path(DIAGNOSTICS_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        wav_path = directory / f"{request_id}.wav"
        wav_tmp = directory / f".{request_id}.wav.tmp"
        with wave.open(str(wav_tmp), "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(WIDTH)
            wav_file.setframerate(RATE)
            wav_file.writeframes(audio)
        wav_tmp.replace(wav_path)

        metrics = _audio_metrics(audio)
        issues = []
        if float(metrics.get("clipping_percent") or 0) >= 0.1:
            issues.append("CLIPPING")
        if metrics.get("tail_active"):
            issues.append("POSSIBLE_END_TRUNCATION")
        if (metrics.get("estimated_snr_db") is not None) and float(metrics["estimated_snr_db"]) < 8.0:
            issues.append("LOW_ESTIMATED_SNR")

        record = {
            "schema_version": 1,
            "id": request_id,
            "started_at": started_at,
            "completed_at": _utc_now(),
            "model": {"id": model.id, "version": model.version, "type": str(model.type.value)},
            "audio": {
                "file": wav_path.name,
                "sample_rate": RATE,
                "sample_width": WIDTH,
                "channels": CHANNELS,
                "metrics": metrics,
                "issues": issues,
            },
            "decoder": decoder,
        }
        json_path = directory / f"{request_id}.json"
        json_tmp = directory / f".{request_id}.json.tmp"
        json_tmp.write_text(json.dumps(record, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
        json_tmp.replace(json_path)
        _LOGGER.info("ACOUSTIC_DIAGNOSTIC %s", json.dumps({"id": request_id, "final_text": decoder.get("final_text", ""), "issues": issues}))
    except Exception:
        _LOGGER.exception("Unable to write acoustic diagnostic")


async def transcribe_kaldi(model: Model, settings: Settings, audio_stream: AsyncIterable[bytes]) -> str:
    """Transcribe text from an audio stream using Kaldi."""
    request_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')[:-3]}Z-{uuid.uuid4().hex[:8]}"
    started_at = _utc_now()
    captured_audio = bytearray()
    decoder: Dict[str, object] = {
        "nbest_count_requested": NBEST,
        "nbest_acoustic_scale": NBEST_ACOUSTIC_SCALE,
        "fuzzy_max_cost": MAX_FUZZY_COST,
        "candidates": [],
        "raw_best_text": "",
        "fuzzy_text": "",
        "fuzzy_cost": None,
        "final_text": "",
        "score_margin": None,
        "word_evidence": [],
        "status": "STARTED",
    }

    model_dir = (settings.models_dir / model.id).absolute()
    train_dir = (settings.train_dir / model.id).absolute()
    lang_dir = train_dir / "data" / "lang"
    graph_dir = train_dir / "graph"
    tools = settings.tools
    model_file = model_dir / "model" / "model" / "final.mdl"
    words_txt = graph_dir / "words.txt"
    online_conf = model_dir / "model" / "online" / "conf" / "online.conf"

    with tempfile.NamedTemporaryFile("wb+") as lattice_file:
        lattice_path = lattice_file.name
        program = "online2-cli-nnet3-decode-faster"
        args = [
            f"--config={online_conf}", f"--max-active={MAX_ACTIVE}",
            f"--lattice-beam={LATTICE_BEAM}", f"--acoustic-scale={DECODE_ACOUSTIC_SCALE}",
            f"--beam={BEAM}", str(model_file), str(graph_dir / "HCLG.fst"),
            str(words_txt), f"ark:{lattice_path}",
        ]
        _LOGGER.debug("%s %s", program, args)
        proc = await asyncio.create_subprocess_exec(
            program, *args, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, env=tools.extended_env,
        )
        assert proc.stdin is not None

        stream_has_chunks = False
        async for chunk in audio_stream:
            captured_audio.extend(chunk)
            proc.stdin.write(chunk)
            await proc.stdin.drain()
            stream_has_chunks = True

        _LOGGER.debug("Stream ended")
        proc.stdin.write_eof()
        await proc.communicate()

        if not stream_has_chunks:
            decoder["status"] = "NO_AUDIO_AFTER_VAD"
            _write_diagnostic(request_id, started_at, model, bytes(captured_audio), decoder)
            return ""

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as language_cost_file, tempfile.NamedTemporaryFile("w+", encoding="utf-8") as acoustic_cost_file:
            nbest_stdout = await tools.async_run_pipeline(
                ["lattice-to-nbest", f"--n={NBEST}", f"--acoustic-scale={NBEST_ACOUSTIC_SCALE}", f"ark:{lattice_path}", "ark:-"],
                ["nbest-to-linear", "ark:-", "ark:/dev/null", "ark,t:-", f"ark,t:{language_cost_file.name}", f"ark,t:{acoustic_cost_file.name}"],
            )
            language_cost_file.flush()
            acoustic_cost_file.flush()
            language_costs = _parse_cost_archive(Path(language_cost_file.name))
            acoustic_costs = _parse_cost_archive(Path(acoustic_cost_file.name))

        int2sym_stdout = await tools.async_run_pipeline(
            [str(tools.egs_utils_dir / "int2sym.pl"), "-f", "2-", str(words_txt)],
            input=nbest_stdout,
        )
        symbol_text = int2sym_stdout.decode(encoding="utf-8")
        _LOGGER.debug("nbest: %s", symbol_text)
        candidates = _parse_candidates(symbol_text, language_costs, acoustic_costs)
        word_boundary = graph_dir / "phones" / "word_boundary.int"
        if word_boundary.exists():
            with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as candidate_ctm_file:
                await tools.async_run_pipeline(
                    ["lattice-to-nbest", f"--n={NBEST}", f"--acoustic-scale={NBEST_ACOUSTIC_SCALE}", f"ark:{lattice_path}", "ark:-"],
                    ["lattice-align-words", str(word_boundary), str(model_file), "ark:-", "ark:-"],
                    ["nbest-to-ctm", "ark:-", candidate_ctm_file.name],
                )
                candidate_ctm_file.flush()
                candidate_ctm_bytes = Path(candidate_ctm_file.name).read_bytes()
            candidate_ctm_symbols = await tools.async_run_pipeline(
                [str(tools.egs_utils_dir / "int2sym.pl"), "-f", "5", str(words_txt)],
                input=candidate_ctm_bytes,
            )
            candidate_timings = _parse_candidate_ctm(candidate_ctm_symbols.decode("utf-8"))
            for candidate in candidates:
                candidate["word_timing"] = candidate_timings.get(str(candidate["key"]), [])
        decoder["candidates"] = candidates
        if candidates:
            decoder["raw_best_text"] = candidates[0]["text"]
        if len(candidates) >= 2 and candidates[0]["total_cost"] is not None and candidates[1]["total_cost"] is not None:
            decoder["score_margin"] = round(float(candidates[1]["total_cost"]) - float(candidates[0]["total_cost"]), 4)

        if word_boundary.exists():
            with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as ctm_file:
                await tools.async_run_pipeline(
                    ["lattice-align-words", str(word_boundary), str(model_file), f"ark:{lattice_path}", "ark:-"],
                    ["lattice-to-ctm-conf", "--decode-mbr=true", f"--acoustic-scale={NBEST_ACOUSTIC_SCALE}", "ark:-", ctm_file.name],
                )
                ctm_file.flush()
                ctm_bytes = Path(ctm_file.name).read_bytes()
            ctm_symbols = await tools.async_run_pipeline(
                [str(tools.egs_utils_dir / "int2sym.pl"), "-f", "5", str(words_txt)],
                input=ctm_bytes,
            )
            decoder["word_evidence"] = _parse_ctm(ctm_symbols.decode("utf-8"))

        fuzzy_result = await _get_fuzzy_text(nbest_stdout, lang_dir, tools)
        if fuzzy_result is None:
            decoder["status"] = "NO_FUZZY_MATCH"
            _write_diagnostic(request_id, started_at, model, bytes(captured_audio), decoder)
            return ""

        text, cost = fuzzy_result
        decoder["fuzzy_text"] = text
        decoder["fuzzy_cost"] = round(cost, 4)
        if cost > MAX_FUZZY_COST:
            decoder["status"] = "FUZZY_COST_TOO_HIGH"
            _write_diagnostic(request_id, started_at, model, bytes(captured_audio), decoder)
            return ""

        final_text = decode_meta(text)
        decoder["final_text"] = final_text
        if not decoder["word_evidence"]:
            final_normalized = final_text.strip().lower()
            for candidate in candidates:
                if str(candidate.get("text", "")).strip().lower() == final_normalized:
                    decoder["word_evidence"] = candidate.get("word_timing", [])
                    break
        decoder["status"] = "OK"
        _write_diagnostic(request_id, started_at, model, bytes(captured_audio), decoder)
        return final_text


async def _get_fuzzy_text(nbest_stdout: bytes, lang_dir: Path, tools: SpeechTools) -> Optional[Tuple[str, float]]:
    fuzzy_fst_path = lang_dir / "G.fuzzy.fst"
    if not fuzzy_fst_path.exists():
        return None
    words_txt = lang_dir / "words.txt"
    input_fst = Fst()
    penalty = 0.0
    with io.StringIO(nbest_stdout.decode("utf-8")) as nbest_file:
        for line in nbest_file:
            line = line.strip()
            if not line:
                continue
            path = line.split()[1:]
            state = input_fst.start
            for symbol in path:
                state = input_fst.next_edge(state, symbol, symbol, log_prob=penalty)
            input_fst.final_states.add(state)
            penalty += NBEST_PENALTY

    with io.StringIO() as input_fst_file:
        input_fst.write(input_fst_file)
        stdout = await tools.async_run_pipeline(
            ["fstcompile"], ["fstcompose", "-", shlex.quote(str(fuzzy_fst_path))],
            ["fstshortestpath"], ["fstrmepsilon"], ["fsttopsort"],
            ["fstproject", "--project_type=output"], ["fstprint", f"--osymbols={words_txt}"],
            input=input_fst_file.getvalue().encode("utf-8"),
        )
        words: List[str] = []
        word_cost = 0.0
        for line in stdout.decode("utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            word = parts[3]
            if len(parts) > 4:
                word_cost += float(parts[4])
            if word != EPS:
                words.append(word)
        if words:
            return " ".join(words), word_cost
        return None
