from __future__ import annotations

import signal
import time
from typing import Any

from .checkpoint import cleanup_orphan_checkpoints, cleanup_temp_files
from .config import Config
from .logging_setup import setup_logger
from .network import parse_host_port_from_url, wait_for_tcp
from .utils import ensure_dir
from .worker import WhisperWorker


def main() -> None:
    cfg = Config.from_env()
    logger = setup_logger(cfg)

    worker = WhisperWorker(cfg, logger)

    def handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        worker.stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    ensure_dir(worker.cfg.input_dir)
    ensure_dir(worker.cfg.output_dir)
    ensure_dir(worker.cfg.log_dir)
    ensure_dir(worker.cfg.checkpoint_dir)
    ensure_dir(worker.cfg.temp_dir)

    host, port = parse_host_port_from_url(worker.cfg.whisper_url)
    logger.info("Waiting for server TCP: %s:%d", host, port)
    if not wait_for_tcp(host, port, worker.cfg.server_wait_timeout, logger):
        raise SystemExit(1)

    cleanup_orphan_checkpoints(worker.cfg, logger)
    cleanup_temp_files(worker.cfg, logger)

    logger.info(
        "Worker started | input=%s | output=%s | checkpoints=%s | resume=%s",
        str(worker.cfg.input_dir),
        str(worker.cfg.output_dir),
        str(worker.cfg.checkpoint_dir),
        worker.cfg.resume_enabled,
    )

    while not worker.stop_event.is_set():
        try:
            files = worker.list_candidate_files()
            if not files:
                time.sleep(worker.cfg.check_interval)
                continue
            for f in files:
                if worker.stop_event.is_set():
                    break
                worker.process_one_file(f)
            time.sleep(worker.cfg.check_interval)
        except KeyboardInterrupt:
            worker.stop_event.set()
            break
        except Exception:
            logger.exception("Unhandled error in main loop")
            time.sleep(worker.cfg.check_interval)


if __name__ == "__main__":
    main()
