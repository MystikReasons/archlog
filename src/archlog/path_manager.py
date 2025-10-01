from typing import Optional, Dict
from pathlib import Path

from archlog.utils import get_datetime_now


class PathManager:
    def __init__(self, config: Optional[Dict[str, str]] = None) -> None:
        paths = config or {}

        self.config_dir = Path(
            paths.get("config-dir", "~/.config/archlog")
        ).expanduser()
        self.changelog_dir = Path(
            paths.get("changelog-dir", "~/archlog/changelog")
        ).expanduser()
        self.logs_dir = Path(
            paths.get("logs-dir", "~/.local/state/archlog/logs")
        ).expanduser()

        self.timestamp_changelog = get_datetime_now("%Y%m%d-%H%M")

    def get_logs_path(self) -> Path:
        return self.logs_dir

    def get_config_path(self, filename: str) -> Path:
        return self.config_dir / filename

    def get_changelog_path(self) -> Path:
        return self.changelog_dir

    def get_changelog_filename(self) -> str:
        return f"{self.timestamp_changelog}-changelog.json"
