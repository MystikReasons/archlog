import sys
import logging
from typing import Optional
from pathlib import Path
from archlog.utils import get_datetime_now


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that gracefully handles encoding issues and mojibake."""

    def emit(self, record):
        try:
            message = str(record.msg)
            # Fix mojibake: reverses incorrect Latin-1 decoding of UTF-8 bytes
            try:
                message = message.encode("latin-1").decode("utf-8")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            record.msg = message
            record.args = None  # prevent double-formatting
            super().emit(record)
        except Exception:
            pass  # never let logging crash the application


class LoggerManager:
    def __init__(self, logs_path: Optional[Path] = None) -> None:
        """Constructor method"""
        self.logs_path = logs_path or self.get_default_logs_path()
        self.logs_path.mkdir(parents=True, exist_ok=True)
        self.setup_logger(self.logs_path)

        # Change the logging level of httpx from INFO to WARNING to reduce log messages.
        logging.getLogger("httpx").setLevel(logging.WARNING)

    def get_default_logs_path(self) -> Path:
        from archlog.path_manager import PathManager

        return PathManager().get_logs_path()

    def setup_logger(self, logs_path: Path) -> None:
        """
        Sets up logging for the application by configuring file and console handlers.

        The function initializes logging to a file and outputs logs to the console.
        Handles potential errors during the setup, such as file access issues.

        :raises Exception: For any other errors encountered during logger setup.
        :return: None
        """
        dt_string_logging = get_datetime_now("%Y-%m-%d_%H-%M-%S")
        logfile = self.logs_path / f"{dt_string_logging}.log"

        try:
            self.logger = logging.getLogger("arch_logger")

            # Guard against duplicate handlers if setup_logger is called more than once
            if self.logger.handlers:
                self.logger.handlers.clear()

            self.logger.setLevel(logging.DEBUG)

            # File handler: full messages, UTF-8, all levels
            file_handler = logging.FileHandler(logfile, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter("%(message)s"))

            # Console handler: safe encoding, INFO and above only
            console_handler = SafeStreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter("%(message)s"))

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

            # Prevent log messages from propagating to the root logger
            self.logger.propagate = False

        except Exception as ex:
            print(f"[Error]: Failed to set up logger: {ex}")
            return None

    def get_logger(self) -> logging.Logger:
        return self.logger
