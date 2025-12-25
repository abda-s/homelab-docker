#!/usr/bin/env python3
from __future__ import annotations

import math
import json
import logging
import mimetypes
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlparse

import requests


# -----------------------------
# Custom Exceptions
# -----------------------------


class ShutdownRequested(Exception):
    """Raised when shutdown is requested during transcription to prevent false success."""
    pass


# -----------------------------
# Utils
# -----------------------------


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def safe_int(v: str, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def safe_float(v: str, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def parse_csv(v: str) -> List[str]:
    parts = [p.strip() for p in v.split(",")]
    return [p for p in parts if p]


def fmt_hhmmss(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_file_signature(path: Path) -> Dict[str, Any]:
    st = path.stat()
    return {"size_bytes": st.st_size, "mtime_ns": st.st_mtime_ns}


def guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    ensure_dir(path.parent)
    with tmp.open("w", encoding=encoding, newline="\n") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    ensure_dir(path.parent)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(payload)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def ffprobe_duration_seconds(path: Path, logger: logging.Logger) -> Optional[float]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
        return float(out) if out else None
    except Exception as e:
        logger.warning("ffprobe failed for %s: %s", path.name, e)
        return None


# -----------------------------
# SSE parsing (matches: `data: {...}`)
# -----------------------------


def iter_sse_data(lines: Iterable[bytes]) -> Iterable[str]:
    data_lines: List[str] = []
    for raw in lines:
        if raw is None:
            continue
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
    if data_lines:
        yield "\n".join(data_lines)


# -----------------------------
# TCP readiness (no /health)
# -----------------------------


def parse_host_port_from_url(url: str) -> Tuple[str, int]:
    u = urlparse(url)
    host = u.hostname or "localhost"
    port = u.port
    if port is None:
        port = 443 if u.scheme == "https" else 80
    return host, port


def wait_for_tcp(host: str, port: int, timeout_s: int, logger: logging.Logger) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except Exception:
            time.sleep(2)
    logger.error("Server not reachable via TCP at %s:%d after %ds", host, port, timeout_s)
    return False


# -----------------------------
# Config
# -----------------------------


@dataclass(frozen=True)
class Config:
    whisper_url: str
    whisper_model: str
    whisper_language: str
    whisper_response_format: str
    whisper_stream: bool

    input_dir: Path
    output_dir: Path
    log_dir: Path
    checkpoint_dir: Path
    temp_dir: Path

    supported_formats: List[str]
    check_interval: int

    max_retries: int
    retry_delay_base: int
    request_timeout: int
    connect_timeout: int
    server_wait_timeout: int

    progress_log_every: int
    checkpoint_save_interval: int

    resume_enabled: bool
    resume_overlap_sec: float
    resume_min_last_end_sec: float

    rename_failed: bool
    complete_at_percent: float

    log_level: str

    @staticmethod
    def from_env() -> "Config":
        supported = os.getenv(
            "SUPPORTED_FORMATS",
            ".mp3,.wav,.m4a,.mp4,.mkv,.flac,.ogg,.webm",
        )
        supported_formats = [s.lower() for s in parse_csv(supported)]
        supported_formats = [s if s.startswith(".") else f".{s}" for s in supported_formats]

        checkpoint_dir = Path(os.getenv("CHECKPOINT_DIR", "/data/checkpoints"))
        temp_dir = Path(os.getenv("TEMP_DIR", str(checkpoint_dir / "tmp")))

        return Config(
            whisper_url=os.getenv(
                "WHISPER_URL",
                "http://localhost:8000/v1/audio/transcriptions",
            ),
            whisper_model=os.getenv("WHISPER_MODEL", "base"),
            whisper_language=os.getenv("WHISPER_LANGUAGE", ""),
            whisper_response_format=os.getenv("WHISPER_RESPONSE_FORMAT", "verbose_json"),
            whisper_stream=os.getenv("WHISPER_STREAM", "true").lower()
            in ("1", "true", "yes", "y"),
            input_dir=Path(os.getenv("INPUT_DIR", "/data/input")),
            output_dir=Path(os.getenv("OUTPUT_DIR", "/data/output")),
            log_dir=Path(os.getenv("LOG_DIR", "/data/logs")),
            checkpoint_dir=checkpoint_dir,
            temp_dir=temp_dir,
            supported_formats=supported_formats,
            check_interval=safe_int(os.getenv("CHECK_INTERVAL", "10"), 10),
            max_retries=safe_int(os.getenv("MAX_RETRIES", "3"), 3),
            retry_delay_base=safe_int(os.getenv("RETRY_DELAY_BASE", "30"), 30),
            request_timeout=safe_int(os.getenv("REQUEST_TIMEOUT", "1800"), 1800),
            connect_timeout=safe_int(os.getenv("CONNECT_TIMEOUT", "10"), 10),
            server_wait_timeout=safe_int(os.getenv("SERVER_WAIT_TIMEOUT", "180"), 180),
            progress_log_every=safe_int(os.getenv("PROGRESS_LOG_EVERY", "10"), 10),
            checkpoint_save_interval=safe_int(
                os.getenv("CHECKPOINT_SAVE_INTERVAL", "10"),
                10,
            ),
            resume_enabled=os.getenv("RESUME_ENABLED", "1").lower()
            in ("1", "true", "yes", "y"),
            resume_overlap_sec=safe_float(os.getenv("RESUME_OVERLAP_SEC", "2.0"), 2.0),
            resume_min_last_end_sec=safe_float(
                os.getenv("RESUME_MIN_LAST_END_SEC", "5.0"),
                5.0,
            ),
            rename_failed=os.getenv("RENAME_FAILED", "1").lower()
            in ("1", "true", "yes", "y"),
            complete_at_percent=safe_float(
                os.getenv("COMPLETE_AT_PERCENT", "0.98"),
                0.98,
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# -----------------------------
# Checkpoints
# -----------------------------


def checkpoint_path_for(cfg: Config, input_file: Path) -> Path:
    safe_name = quote(input_file.name, safe="")
    return cfg.checkpoint_dir / f"{safe_name}.json"


def load_checkpoint(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def cleanup_orphan_checkpoints(cfg: Config, logger: logging.Logger) -> int:
    ensure_dir(cfg.checkpoint_dir)
    removed = 0
    for cp in cfg.checkpoint_dir.glob("*.json"):
        data = load_checkpoint(cp)
        if not data:
            try:
                cp.unlink()
                removed += 1
            except Exception:
                pass
            continue
        file_path = data.get("file_path")
        if not file_path or not Path(file_path).exists():
            try:
                cp.unlink()
                removed += 1
            except Exception:
                pass
    logger.info("Orphan checkpoint cleanup: removed=%d", removed)
    return removed


# -----------------------------
# Resume: cut media from offset
# -----------------------------


def file_size_mb(p: Path) -> float:
    try:
        return p.stat().st_size / (1024 * 1024)
    except Exception:
        return float("nan")


def ffmpeg_cut_resume_chunk(
    src: Path,
    dst_base: Path,
    offset_sec: float,
    logger: logging.Logger,
) -> Path:
    """
    Creates a smaller resume chunk than WAV to reduce "resume not proceeding"
    time (upload + server decode delay).

    Strategy:
      1) Try audio stream copy into MKV (fast, tiny): -c:a copy
      2) Fallback to 16k mono FLAC (smaller than WAV, accurate)
    """
    ensure_dir(dst_base.parent)

    # 1) COPY -> .mkv (audio only)
    dst_copy = dst_base.with_suffix(".mkv")
    cmd_copy = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{offset_sec:.3f}",
        "-i",
        str(src),
        "-vn",
        "-c:a",
        "copy",
        str(dst_copy),
    ]
    logger.info(
        "Creating resume chunk (copy) at %.3fs: %s",
        offset_sec,
        dst_copy.name,
    )
    try:
        if dst_copy.exists():
            dst_copy.unlink()
        subprocess.check_call(cmd_copy)
        logger.info("Resume chunk ready: %s (%.1f MB)", dst_copy.name, file_size_mb(dst_copy))
        return dst_copy
    except Exception as e:
        logger.warning("Copy-cut failed (%s). Falling back to FLAC re-encode.", e)
        try:
            if dst_copy.exists():
                dst_copy.unlink()
        except Exception:
            pass

    # 2) FLAC fallback (accurate + much smaller than WAV)
    dst_flac = dst_base.with_suffix(".flac")
    cmd_flac = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{offset_sec:.3f}",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "flac",
        str(dst_flac),
    ]
    logger.info(
        "Creating resume chunk (flac) at %.3fs: %s",
        offset_sec,
        dst_flac.name,
    )
    if dst_flac.exists():
        dst_flac.unlink()
    subprocess.check_call(cmd_flac)
    logger.info("Resume chunk ready: %s (%.1f MB)", dst_flac.name, file_size_mb(dst_flac))
    return dst_flac


def seg_key(start: float, end: float, text: str) -> Tuple[float, float, str]:
    # Round timestamps to milliseconds to dedupe reliably across retries.
    return (round(start, 3), round(end, 3), text.strip())


# -----------------------------
# Worker
# -----------------------------


class WhisperWorker:
    def __init__(self, cfg: Config, logger: logging.Logger):
        self.cfg = cfg
        self.logger = logger
        self.stop_event = threading.Event()

    def list_candidate_files(self) -> List[Path]:
        ensure_dir(self.cfg.input_dir)
        out: List[Path] = []
        for p in self.cfg.input_dir.iterdir():
            if not p.is_file():
                continue
            if p.name.startswith("processed_"):
                continue
            if p.suffix.lower() in self.cfg.supported_formats:
                out.append(p)
        return sorted(out, key=lambda x: x.name.lower())

    def rename_processed(self, input_path: Path) -> Path:
        parent = input_path.parent
        target = parent / f"processed_{input_path.name}"
        if target.exists():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = parent / f"processed_{ts}_{input_path.name}"
        os.replace(input_path, target)
        return target

    def rename_failed(self, input_path: Path) -> Path:
        parent = input_path.parent
        target = parent / f"failed_{input_path.name}"
        if target.exists():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = parent / f"failed_{ts}_{input_path.name}"
        os.replace(input_path, target)
        return target

    def save_outputs(
        self,
        input_path: Path,
        transcript_text: str,
        segments: List[Dict[str, Any]],
        audio_duration: Optional[float],
        elapsed_s: float,
    ) -> Tuple[Path, Path]:
        base = input_path.stem
        clean_path = self.cfg.output_dir / f"{base}.txt"
        ts_path = self.cfg.output_dir / f"{base}_timestamped.txt"

        atomic_write_text(clean_path, transcript_text.strip() + "\n", encoding="utf-8")

        lines: List[str] = []
        lines.append(f"file: {input_path.name}")
        if audio_duration is not None:
            lines.append(f"duration_sec: {audio_duration:.3f}")
        lines.append(f"model: {self.cfg.whisper_model}")
        if self.cfg.whisper_language:
            lines.append(f"language: {self.cfg.whisper_language}")
        lines.append(f"elapsed_sec: {elapsed_s:.3f}")
        lines.append(f"segments: {len(segments)}")
        lines.append("")
        lines.append("transcript:")
        lines.append(transcript_text.strip())
        lines.append("")
        lines.append("segments_timestamped:")
        for s in segments:
            lines.append(
                f"[{float(s['start']):09.3f} - {float(s['end']):09.3f}] {s['text']}"
            )

        atomic_write_text(ts_path, "\n".join(lines).strip() + "\n", encoding="utf-8")
        return clean_path, ts_path

    def _log_progress(
        self,
        file_name: str,
        started_at: float,
        segments_done: int,
        last_end_sec: Optional[float],
        audio_duration: Optional[float],
        last_event_at: Optional[float],
    ) -> None:
        elapsed = int(time.time() - started_at)
        last_event_ago = None
        if last_event_at is not None:
            last_event_ago = int(time.time() - last_event_at)

        if audio_duration and audio_duration > 0 and last_end_sec is not None:
            pct_done = max(0.0, min(100.0, (last_end_sec / audio_duration) * 100.0))
            if last_event_ago is None:
                self.logger.info(
                    "Transcribing: %s | segments_done=%d | done=%.1f%% | elapsed=%s",
                    file_name,
                    segments_done,
                    pct_done,
                    fmt_hhmmss(elapsed),
                )
            else:
                self.logger.info(
                    "Transcribing: %s | segments_done=%d | done=%.1f%% | elapsed=%s | last_event_ago=%ss",
                    file_name,
                    segments_done,
                    pct_done,
                    fmt_hhmmss(elapsed),
                    last_event_ago,
                )
        else:
            if last_event_ago is None:
                self.logger.info(
                    "Transcribing: %s | segments_done=%d | elapsed=%s",
                    file_name,
                    segments_done,
                    fmt_hhmmss(elapsed),
                )
            else:
                self.logger.info(
                    "Transcribing: %s | segments_done=%d | elapsed=%s | last_event_ago=%ss",
                    file_name,
                    segments_done,
                    fmt_hhmmss(elapsed),
                    last_event_ago,
                )

    def _transcribe_sse_and_merge(
        self,
        target_path: Path,
        input_path: Path,
        cp_path: Path,
        started_at: float,
        audio_duration: Optional[float],
        segments_map: Dict[Tuple[float, float, str], Dict[str, Any]],
        resume_offset_sec: float,
        drop_ends_leq_sec: Optional[float],
    ) -> str:
        """
        Streams SSE and merges segments into segments_map.
        - If resume_offset_sec > 0 and server returns segment times starting near 0,
          we shift times by resume_offset_sec.
        - If drop_ends_leq_sec is set (original last_end), we drop overlapped segments.
        Returns latest text from server events (best-effort).
        """
        mime = guess_mime(target_path)
        headers = {"Accept": "text/event-stream"}

        form: List[Tuple[str, str]] = [
            ("model", self.cfg.whisper_model),
            ("response_format", self.cfg.whisper_response_format),
            ("stream", "true"),
        ]
        if self.cfg.whisper_language:
            form.append(("language", self.cfg.whisper_language))

        latest_text = ""

        progress_lock = threading.Lock()
        existing_last_end = None
        if segments_map:
            existing_last_end = max(v["end"] for v in segments_map.values())
        progress_state = {
            "segments_done": len(segments_map),
            "last_end_sec": existing_last_end,
        }
        last_event_at: Optional[float] = None

        progress_stop = threading.Event()

        def progress_thread() -> None:
            while not self.stop_event.is_set() and not progress_stop.is_set():
                time.sleep(max(1, self.cfg.progress_log_every))
                with progress_lock:
                    seg_done = int(progress_state["segments_done"])
                    last_end = progress_state["last_end_sec"]
                self._log_progress(
                    input_path.name,
                    started_at,
                    seg_done,
                    last_end,
                    audio_duration,
                    last_event_at,
                )

        t = threading.Thread(target=progress_thread, daemon=True)
        t.start()

        last_checkpoint_write = 0.0

        try:
            with target_path.open("rb") as f:
                files = {"file": (target_path.name, f, mime)}
                with requests.post(
                    self.cfg.whisper_url,
                    data=form,
                    files=files,
                    headers=headers,
                    stream=True,
                    timeout=self.cfg.request_timeout,
                ) as resp:
                    resp.raise_for_status()

                    for payload in iter_sse_data(resp.iter_lines()):
                        if self.stop_event.is_set():
                            raise ShutdownRequested("Shutdown requested during transcription")
                        last_event_at = time.time()

                        if payload.strip() in ("[DONE]", "DONE"):
                            break

                        try:
                            event = json.loads(payload)
                        except Exception:
                            continue

                        if isinstance(event.get("text"), str):
                            latest_text = event["text"]

                        segs = event.get("segments")
                        if not isinstance(segs, list):
                            continue

                        shift = resume_offset_sec if resume_offset_sec > 0 else 0.0

                        changed = False
                        last_end = None

                        for s in segs:
                            try:
                                start = float(s.get("start", 0.0)) + shift
                                end = float(s.get("end", 0.0)) + shift
                                text = (s.get("text") or "").strip()
                            except Exception:
                                continue

                            if drop_ends_leq_sec is not None:
                                # Drop overlap (tiny epsilon)
                                if end <= drop_ends_leq_sec + 0.05:
                                    continue

                            key = seg_key(start, end, text)
                            segments_map[key] = {"start": start, "end": end, "text": text}
                            changed = True
                            last_end = end if last_end is None else max(last_end, end)

                        if changed:
                            seg_done = len(segments_map)
                            global_last_end = (
                                max(v["end"] for v in segments_map.values())
                                if segments_map
                                else None
                            )
                            with progress_lock:
                                progress_state["segments_done"] = seg_done
                                progress_state["last_end_sec"] = global_last_end

                            now = time.time()
                            if now - last_checkpoint_write >= self.cfg.checkpoint_save_interval:
                                last_checkpoint_write = now
                                seg_list = sorted(
                                    segments_map.values(),
                                    key=lambda x: (x["start"], x["end"]),
                                )
                                cp = load_checkpoint(cp_path) or {}
                                cp["state"] = "in_progress"
                                cp["updated_at"] = utc_now_iso()
                                cp["segments"] = seg_list
                                cp["last_end_sec"] = (
                                    seg_list[-1]["end"] if seg_list else None
                                )
                                cp["latest_text"] = latest_text
                                atomic_write_json(cp_path, cp)

            if self.stop_event.is_set():
                raise ShutdownRequested("Shutdown requested at end of transcription")

            return latest_text
        finally:
            progress_stop.set()
            try:
                t.join(timeout=1)
            except Exception:
                pass

    def process_one_file(self, input_path: Path) -> None:
        cp_path = checkpoint_path_for(self.cfg, input_path)
        sig = get_file_signature(input_path)

        ensure_dir(self.cfg.checkpoint_dir)
        ensure_dir(self.cfg.output_dir)
        ensure_dir(self.cfg.temp_dir)

        cp = load_checkpoint(cp_path) or {}
        if cp.get("file_signature") != sig:
            cp = {
                "version": 3,
                "file_name": input_path.name,
                "file_path": str(input_path),
                "file_signature": sig,
                "attempts": 0,
                "state": "pending",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "segments": [],
                "last_end_sec": None,
                "latest_text": "",
            }
            atomic_write_json(cp_path, cp)

        audio_duration = ffprobe_duration_seconds(input_path, self.logger)

        segments_map: Dict[Tuple[float, float, str], Dict[str, Any]] = {}
        for s in cp.get("segments") or []:
            try:
                start = float(s["start"])
                end = float(s["end"])
                text = (s["text"] or "").strip()
                segments_map[seg_key(start, end, text)] = {
                    "start": start,
                    "end": end,
                    "text": text,
                }
            except Exception:
                continue

        attempt = int(cp.get("attempts", 0))
        last_end_sec = cp.get("last_end_sec")
        try:
            last_end_sec = float(last_end_sec) if last_end_sec is not None else None
        except Exception:
            last_end_sec = None

        while attempt < self.cfg.max_retries and not self.stop_event.is_set():
            attempt += 1

            started_at = time.time()
            cp_live = load_checkpoint(cp_path) or {}
            cp_live["attempts"] = attempt
            cp_live["state"] = "in_progress"
            cp_live["updated_at"] = utc_now_iso()
            atomic_write_json(cp_path, cp_live)

            resume_offset_sec = 0.0
            drop_ends_leq_sec = None
            target_path = input_path
            tmp_path = None

            # Decide resume mode
            if (
                self.cfg.resume_enabled
                and audio_duration
                and audio_duration > 0
                and last_end_sec is not None
                and last_end_sec >= self.cfg.resume_min_last_end_sec
                and last_end_sec < audio_duration - 1.0
            ):
                resume_offset_sec = max(0.0, last_end_sec - self.cfg.resume_overlap_sec)
                drop_ends_leq_sec = last_end_sec

                tmp_base = self.cfg.temp_dir / f"resume_{quote(input_path.name, safe='')}"
                try:
                    for ext in (".wav", ".flac", ".mkv"):
                        p = tmp_base.with_suffix(ext)
                        if p.exists():
                            p.unlink()
                except Exception:
                    pass

                tmp_path = ffmpeg_cut_resume_chunk(
                    src=input_path,
                    dst_base=tmp_base,
                    offset_sec=resume_offset_sec,
                    logger=self.logger,
                )
                target_path = tmp_path

                self.logger.info(
                    "Uploading resume chunk: %s (%.1f MB)",
                    tmp_path.name,
                    file_size_mb(tmp_path),
                )

                self.logger.info(
                    "Resume enabled for %s | last_end=%.3fs | offset=%.3fs | overlap=%.3fs",
                    input_path.name,
                    last_end_sec,
                    resume_offset_sec,
                    self.cfg.resume_overlap_sec,
                )
            else:
                self.logger.info("Starting transcription from beginning: %s", input_path.name)

            try:
                latest_text = self._transcribe_sse_and_merge(
                    target_path=target_path,
                    input_path=input_path,
                    cp_path=cp_path,
                    started_at=started_at,
                    audio_duration=audio_duration,
                    segments_map=segments_map,
                    resume_offset_sec=resume_offset_sec,
                    drop_ends_leq_sec=drop_ends_leq_sec,
                )

                seg_list = sorted(segments_map.values(), key=lambda x: (x["start"], x["end"]))

                # Completion threshold check
                if audio_duration and audio_duration > 0 and seg_list:
                    global_last_end = seg_list[-1]["end"]
                    pct = global_last_end / audio_duration
                    if pct < self.cfg.complete_at_percent:
                        raise RuntimeError(
                            f"Incomplete transcription: {pct:.3%} < {self.cfg.complete_at_percent:.0%}"
                        )

                # Build final transcript from segments (more reliable than partial `text`)
                transcript = "".join([s["text"] for s in seg_list]).strip()
                if not transcript and isinstance(latest_text, str):
                    transcript = latest_text.strip()

                elapsed = time.time() - started_at

                self.save_outputs(
                    input_path=input_path,
                    transcript_text=transcript,
                    segments=seg_list,
                    audio_duration=audio_duration,
                    elapsed_s=elapsed,
                )
                processed = self.rename_processed(input_path)

                try:
                    cp_path.unlink(missing_ok=True)
                except Exception:
                    pass

                self.logger.info(
                    "SUCCESS: %s | segments=%d | elapsed=%.2fs",
                    processed.name,
                    len(seg_list),
                    elapsed,
                )
                return

            except ShutdownRequested:
                self.logger.warning("Shutdown requested, saving checkpoint and aborting")
                # Save current progress
                seg_list = sorted(segments_map.values(), key=lambda x: (x["start"], x["end"]))
                cp_shutdown = load_checkpoint(cp_path) or {}
                cp_shutdown["state"] = "interrupted"
                cp_shutdown["updated_at"] = utc_now_iso()
                cp_shutdown["segments"] = seg_list
                cp_shutdown["last_end_sec"] = seg_list[-1]["end"] if seg_list else None
                cp_shutdown["latest_text"] = latest_text if 'latest_text' in locals() else ""
                atomic_write_json(cp_path, cp_shutdown)
                raise

            except KeyboardInterrupt:
                self.stop_event.set()
                raise
            except Exception as e:
                self.logger.exception(
                    "FAIL: %s | attempt=%d/%d | err=%s",
                    input_path.name,
                    attempt,
                    self.cfg.max_retries,
                    str(e),
                )

                # Persist current segments on failure
                seg_list = sorted(segments_map.values(), key=lambda x: (x["start"], x["end"]))
                cp_fail = load_checkpoint(cp_path) or {}
                cp_fail["state"] = "failed_attempt"
                cp_fail["updated_at"] = utc_now_iso()
                cp_fail["last_error"] = str(e)
                cp_fail["segments"] = seg_list
                cp_fail["last_end_sec"] = seg_list[-1]["end"] if seg_list else None
                atomic_write_json(cp_path, cp_fail)

                # Update last_end_sec for next retry decision
                last_end_sec = cp_fail.get("last_end_sec")
                try:
                    last_end_sec = float(last_end_sec) if last_end_sec is not None else None
                except Exception:
                    last_end_sec = None

                if attempt >= self.cfg.max_retries:
                    break

                delay = self.cfg.retry_delay_base * (2 ** (attempt - 1))
                self.logger.info("Retrying %s in %ds", input_path.name, delay)
                end_wait = time.time() + delay
                while time.time() < end_wait and not self.stop_event.is_set():
                    time.sleep(1)

            finally:
                if tmp_path is not None:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass

        cp_final = load_checkpoint(cp_path) or {}
        cp_final["state"] = "permanent_failed"
        cp_final["updated_at"] = utc_now_iso()
        atomic_write_json(cp_path, cp_final)

        if self.cfg.rename_failed and input_path.exists():
            failed_path = self.rename_failed(input_path)
            cp_final = load_checkpoint(cp_path) or cp_final
            cp_final["file_path"] = str(failed_path)
            atomic_write_json(cp_path, cp_final)
            self.logger.error("PERMANENT FAIL: %s -> %s", input_path.name, failed_path.name)
        else:
            self.logger.error("PERMANENT FAIL: %s", input_path.name)

    def run(self) -> None:
        ensure_dir(self.cfg.input_dir)
        ensure_dir(self.cfg.output_dir)
        ensure_dir(self.cfg.log_dir)
        ensure_dir(self.cfg.checkpoint_dir)
        ensure_dir(self.cfg.temp_dir)

        host, port = parse_host_port_from_url(self.cfg.whisper_url)
        self.logger.info("Waiting for server TCP: %s:%d", host, port)
        if not wait_for_tcp(host, port, self.cfg.server_wait_timeout, self.logger):
            raise SystemExit(1)

        cleanup_orphan_checkpoints(self.cfg, self.logger)

        self.logger.info(
            "Worker started | input=%s | output=%s | checkpoints=%s | resume=%s",
            str(self.cfg.input_dir),
            str(self.cfg.output_dir),
            str(self.cfg.checkpoint_dir),
            self.cfg.resume_enabled,
        )

        while not self.stop_event.is_set():
            try:
                files = self.list_candidate_files()
                if not files:
                    time.sleep(self.cfg.check_interval)
                    continue
                for f in files:
                    if self.stop_event.is_set():
                        break
                    self.process_one_file(f)
                time.sleep(self.cfg.check_interval)
            except KeyboardInterrupt:
                self.stop_event.set()
                break
            except Exception:
                self.logger.exception("Unhandled error in main loop")
                time.sleep(self.cfg.check_interval)


# -----------------------------
# Logging
# -----------------------------


def setup_logger(cfg: Config) -> logging.Logger:
    ensure_dir(cfg.log_dir)
    logger = logging.getLogger("whisper-worker")
    logger.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
    logger.propagate = False

    for h in list(logger.handlers):
        logger.removeHandler(h)

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        cfg.log_dir / "worker.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


# -----------------------------
# Main
# -----------------------------


def main() -> None:
    cfg = Config.from_env()
    logger = setup_logger(cfg)

    worker = WhisperWorker(cfg, logger)

    def handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        worker.stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    worker.run()


if __name__ == "__main__":
    main()
