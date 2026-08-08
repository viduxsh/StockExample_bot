import logging
import os
from logging.handlers import RotatingFileHandler

DATA_DIR = "data"
_configured = False


def setup_logging() -> None:
    """Configure root logger with console + rotating file handlers.

    Call this ONCE at application startup (in bot.py __main__).
    After calling this, every module can simply use:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    """
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(DATA_DIR, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # capture everything; handlers filter

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console handler (INFO+) ──────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    # ── bot.log  — all INFO+ messages, rotating 5 MB × 3 files ─────────────
    bot_log_path = os.path.join(DATA_DIR, "bot.log")
    file_handler = RotatingFileHandler(
        bot_log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    # ── errors.log — ERROR+ only, rotating 2 MB × 3 files ──────────────────
    error_log_path = os.path.join(DATA_DIR, "errors.log")
    error_handler = RotatingFileHandler(
        error_log_path,
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)

    # Suppress spammy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging system initialised — bot.log / errors.log in '%s/'", DATA_DIR
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. setup_logging() must have been called first."""
    return logging.getLogger(name)
