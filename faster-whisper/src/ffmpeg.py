from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

import re
import time
from .utils import ensure_dir, fmt_hhmmss


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


def get_mean_volume(path: Path, logger: logging.Logger) -> float:
    """
    Returns the mean volume in dB using ffmpeg volumedetect filter.
    Returns -91.0 (silence) on failure.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(path),
        "-af",
        "volumedetect",
        "-vn",
        "-sn",
        "-dn",
        "-f",
        "null",
        "-",
    ]
    try:
        # volumedetect output goes to stderr
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        for line in out.splitlines():
            if "mean_volume:" in line:
                # [Parsed_volumedetect_0 @ ...] mean_volume: -25.4 dB
                parts = line.split("mean_volume:")
                if len(parts) > 1:
                    val_str = parts[1].strip().split(" ")[0]
                    return float(val_str)
    except Exception as e:
        logger.warning("get_mean_volume failed for %s: %s", path.name, e)
    
    return -91.0


def remove_silence(
    src: Path,
    dst: Path,
    logger: logging.Logger,
    min_silence_duration: float = 0.5,
) -> bool:
    """
    Removes silence from audio using dynamic thresholding.
    Threshold = mean_volume - 20dB.
    """
    mean_vol = get_mean_volume(src, logger)
    # If mean volume is very low (silence), just copy
    if mean_vol < -70:
        logger.info("Audio is already silent (mean=%.1fdB), skipping VAD", mean_vol)
        return False

    threshold_db = mean_vol - 20.0
    # Cap threshold to avoid cutting too aggressively or not enough
    # e.g. if mean is -10, thresh is -30. If mean is -40, thresh is -60.
    # Let's keep it reasonable: max -20dB, min -60dB
    threshold_db = max(-60.0, min(-20.0, threshold_db))

    ensure_dir(dst.parent)
    if dst.exists():
        dst.unlink()

    # silenceremove=stop_periods=-1:stop_duration=0.5:stop_threshold=-30dB
    # stop_periods=-1 means remove all silence periods
    filter_str = (
        f"silenceremove=stop_periods=-1:"
        f"stop_duration={min_silence_duration}:"
        f"stop_threshold={threshold_db:.1f}dB"
    )

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress", "pipe:2", # Output machine-readable progress to stderr
        "-i",
        str(src),
        "-af",
        filter_str,
        "-c:a",
        "flac",  # Use FLAC for lossless intermediate
        str(dst),
    ]
    
    logger.info(
        "Removing silence: %s -> %s | mean=%.1fdB | thresh=%.1fdB",
        src.name,
        dst.name,
        mean_vol,
        threshold_db,
    )

    # Get total duration for percentage calculation
    total_duration = ffprobe_duration_seconds(src, logger) or 0.0

    try:
        # Use Popen to stream stderr for progress
        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        
        last_log_time = time.time()
        
        # Regex to capture out_time=HH:MM:SS.ms (from -progress)
        # e.g. out_time=00:00:05.120000
        time_pattern = re.compile(r"out_time=(\d{2}:\d{2}:\d{2}\.\d+)")

        if process.stderr:
            for line in process.stderr:
                # Still check for completion/errors
                if not line:
                    continue
                
                now = time.time()
                if now - last_log_time >= 10.0:  # Log every 10 seconds
                    match = time_pattern.search(line)
                    if match:
                        time_str = match.group(1)
                        # Extract hours, minutes, seconds from HH:MM:SS.ms
                        try:
                            h, m, s = time_str.split(":")
                            seconds = int(h) * 3600 + int(m) * 60 + float(s)
                            
                            if total_duration > 0:
                                pct = (seconds / total_duration) * 100
                                logger.info(
                                    "VAD Progress: %s / %s (%.1f%%)",
                                    fmt_hhmmss(int(seconds)),
                                    fmt_hhmmss(int(total_duration)),
                                    pct
                                )
                            else:
                                logger.info("VAD Progress: %s", fmt_hhmmss(int(seconds)))
                            
                            last_log_time = now
                        except Exception:
                            pass # Parse error, skip log

        ret = process.wait()
        if ret != 0:
            raise subprocess.CalledProcessError(ret, cmd)

        return True
    except Exception as e:
        logger.error("remove_silence failed: %s", e)
        if dst.exists():
            dst.unlink()
        return False
