from typing import Optional
import logging
from pathlib import Path

from archlog.utils import get_datetime_now


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
            logging.basicConfig(
                filename=logfile,
                format="%(asctime)s %(message)s",
                filemode="w",
            )

            self.logger = logging.getLogger()
            self.logger.setLevel(logging.DEBUG)

            # Output the logging also to the console
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            stream_format = logging.Formatter("%(message)s")
            stream_handler.setFormatter(stream_format)
            self.logger.addHandler(stream_handler)

        except Exception as ex:
            print(f"[Error]: Failed to set up logger: {ex}")
            return None

    def get_logger(self) -> logging.Logger:
        return self.logger
