from __future__ import annotations

import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


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

def seg_key(start: float, end: float, text: str) -> Tuple[float, float, str]:
    # Round timestamps to milliseconds to dedupe reliably across retries.
    return (round(start, 3), round(end, 3), text.strip())


def soft_delete(path: Path) -> None:
    """
    Renames the file to 'deleted_{timestamp}_{original_name}' instead of deleting it.
    """
    if not path.exists():
        return
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    new_name = f"deleted_{timestamp}_{path.name}"
    new_path = path.parent / new_name
    
    try:
        os.replace(path, new_path)
    except Exception:
        pass
