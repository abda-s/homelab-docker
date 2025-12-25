from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .checkpoint import checkpoint_path_for, load_checkpoint
from .config import Config
from .exceptions import ShutdownRequested
from .ffmpeg import (
    ffmpeg_cut_resume_chunk,
    ffprobe_duration_seconds,
    file_size_mb,
    remove_silence,
)
from .utils import (
    atomic_write_json,
    atomic_write_text,
    ensure_dir,
    fmt_hhmmss,
    get_file_signature,
    guess_mime,
    seg_key,
    soft_delete,
    utc_now_iso,
)
from .whisper_api import iter_sse_data


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
            processed_time = fmt_hhmmss(int(last_end_sec))
            total_time = fmt_hhmmss(int(audio_duration))
            
            if last_event_ago is None:
                # Use sys.stderr for in-place updates. 
                # \033[K clears the rest of the line (ANSI escape), optional but good for cleanliness
                msg = f"\rTranscribing: {file_name} | Segments: {segments_done} | Progress: {processed_time} / {total_time} ({pct_done:.1f}%) | Elapsed: {fmt_hhmmss(elapsed)}"
                sys.stderr.write(msg)
                sys.stderr.flush()
            else:
                msg = f"\rTranscribing: {file_name} | Segments: {segments_done} | Progress: {processed_time} / {total_time} ({pct_done:.1f}%) | Elapsed: {fmt_hhmmss(elapsed)} | Stall: {last_event_ago}s"
                sys.stderr.write(msg)
                sys.stderr.flush()
        else:
            # Fallback if no duration known
            msg = f"\rTranscribing: {file_name} | Segments: {segments_done} | Elapsed: {fmt_hhmmss(elapsed)}"
            if last_event_ago is not None:
                msg += f" | Stall: {last_event_ago}s"
            sys.stderr.write(msg)
            sys.stderr.flush()

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

            atomic_write_json(cp_path, cp)
        
        # --- VAD Step ---
        # We create a clean version of the file (silence removed) and use THAT for everything.
        clean_path = self.cfg.temp_dir / f"clean_{input_path.name}"
        # Ensure clean path has correct extension (WAV is faster to write than FLAC)
        clean_path = clean_path.with_suffix(".wav")
        
        use_path = input_path
        
        try:
            # Only run VAD if we haven't already (or if clean file missing)
            # But since we clean up clean_path at end, we likely need to re-run.
            # Optimization: could check if clean_path exists and is recent?
            # For now, just run it.
            self.logger.info("VAD: Removing silence from %s ...", input_path.name)
            if remove_silence(input_path, clean_path, self.logger):
                use_path = clean_path
                self.logger.info("Using silence-removed file: %s", use_path.name)
            else:
                self.logger.info("VAD skipped or failed, using original: %s", use_path.name)
        except Exception as e:
            self.logger.warning("VAD error (%s), using original file", e)
            use_path = input_path

        audio_duration = ffprobe_duration_seconds(use_path, self.logger)

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
            target_path = use_path
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
                self.logger.info("Resuming %s from %.1fs ...", input_path.name, last_end_sec)
                resume_offset_sec = max(0.0, last_end_sec - self.cfg.resume_overlap_sec)
                drop_ends_leq_sec = last_end_sec

                tmp_base = self.cfg.temp_dir / f"resume_{use_path.name}"
                try:
                    for ext in (".wav", ".flac", ".mkv"):
                        p = tmp_base.with_suffix(ext)
                        if p.exists():
                            soft_delete(p)
                except Exception:
                    pass

                self.logger.info("Cutting resume chunk (offset=%.1fs) ...", resume_offset_sec)
                tmp_path = ffmpeg_cut_resume_chunk(
                    src=use_path,
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
                    use_path.name,
                    last_end_sec,
                    resume_offset_sec,
                    self.cfg.resume_overlap_sec,
                )
            else:
                self.logger.info("Starting transcription from beginning: %s", use_path.name)

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
                # Fix: Join with space to prevent run-on words
                transcript = " ".join([s["text"].strip() for s in seg_list]).strip()
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
                    soft_delete(cp_path)
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
                cp_shutdown["latest_text"] = latest_text if "latest_text" in locals() else ""
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
                        soft_delete(tmp_path)
                    except Exception:
                        pass
                
                # Cleanup VAD file if we created one
                if use_path == clean_path:
                    try:
                        soft_delete(clean_path)
                    except Exception:
                        pass

        # Finish progress line with a newline
        sys.stderr.write("\n")
        sys.stderr.flush()
        
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
