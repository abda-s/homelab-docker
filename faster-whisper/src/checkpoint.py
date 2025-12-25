from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from .config import Config
from .utils import ensure_dir, soft_delete


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
                soft_delete(cp)
                removed += 1
            except Exception:
                pass
            continue
        file_path = data.get("file_path")
        if not file_path or not Path(file_path).exists():
            try:
                soft_delete(cp)
                removed += 1
            except Exception:
                pass
    logger.info("Orphan checkpoint cleanup: removed=%d", removed)
    return removed


def cleanup_temp_files(cfg: Config, logger: logging.Logger) -> int:
    """
    Deletes ALL files in the temp directory on startup.
    This prevents disk usage accumulation from crashed jobs.
    """
    ensure_dir(cfg.temp_dir)
    removed = 0
    # Iterate over all files in temp_dir
    for p in cfg.temp_dir.iterdir():
        if p.is_file():
            try:
                p.unlink() # Hard delete
                removed += 1
            except Exception as e:
                logger.warning("Failed to delete temp file %s: %s", p.name, e)
    
    if removed > 0:
        logger.info("Startup temp cleanup: removed %d files from %s", removed, cfg.temp_dir)
    return removed
