from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from .utils import ensure_dir


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
