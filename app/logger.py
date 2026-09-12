"""
Cấu hình logging tập trung cho toàn bộ ứng dụng.

Thay thế print() bằng logging module tiêu chuẩn:
  - Có level (DEBUG, INFO, WARNING, ERROR)
  - Có timestamp
  - Ghi ra console + file log (tuỳ chọn)
  - Định dạng nhất quán
"""
import logging
import sys
from pathlib import Path
from app.config import get_settings

settings = get_settings()

# Thư mục chứa file log
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "chatbot.log"

# Định dạng log
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """
    Thiết lập logging cho toàn bộ ứng dụng.
    Gọi 1 lần khi startup.

    Returns:
        Root logger đã được cấu hình.
    """
    level = logging.DEBUG if settings.debug else logging.INFO

    # Root logger
    root_logger = logging.getLogger("chatbot")
    root_logger.setLevel(level)

    # Xóa handler cũ nếu có (tránh duplicate khi reload)
    root_logger.handlers.clear()

    # Console handler (stdout, UTF-8 an toàn)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # File handler (ghi ra file, UTF-8)
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Lấy logger cho một module cụ thể.

    Usage:
        from app.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Tin nhắn")
        logger.error("Lỗi", exc_info=True)
    """
    return logging.getLogger(f"chatbot.{name}")
