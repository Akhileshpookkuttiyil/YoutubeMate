import logging
import os
import sys
from config import get_log_file_path


class FlushingFileHandler(logging.FileHandler):
    """FileHandler that flushes immediately after emit to ensure real-time logging."""
    def emit(self, record):
        super().emit(record)
        self.flush()


def setup_logger(name="YouTubeMate", level=logging.INFO):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    log_file = get_log_file_path()
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = FlushingFileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        fh.setLevel(level)
        logger.addHandler(fh)
    except Exception as e:
        sys.stderr.write(f"Warning: Could not configure file logger at {log_file}: {e}\n")

    # Add console handler only in debug/development mode
    if not getattr(sys, 'frozen', False):
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        ch.setLevel(logging.WARNING)
        logger.addHandler(ch)

    return logger


logger = setup_logger()
