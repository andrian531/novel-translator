import os
import logging
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scraper_logs")
os.makedirs(LOG_DIR, exist_ok=True)

_log_date = datetime.now().strftime("%Y%m%d")
LOG_FILE = os.path.join(LOG_DIR, f"scraper_{_log_date}.log")

# Gunakan named logger, bukan root logger via basicConfig
# basicConfig hanya bekerja jika root logger belum punya handler —
# requests/playwright sering pre-configure root logger sehingga basicConfig jadi no-op.
logger = logging.getLogger("novel_translator")
logger.setLevel(logging.DEBUG)
logger.propagate = False  # Jangan propagate ke root (hindari noise dari requests/playwright)

if not logger.handlers:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(_fh)


def get_log_path():
    return LOG_FILE


def tail_log(n=30):
    """Return the last n lines of today's log file."""
    if not os.path.exists(LOG_FILE):
        return "(log kosong)"
    with open(LOG_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-n:])
