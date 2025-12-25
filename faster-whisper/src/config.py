from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .utils import parse_csv, safe_float, safe_int


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
