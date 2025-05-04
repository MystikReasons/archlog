from typing import Dict, Any, List, Tuple, NamedTuple
import json
import os
from pathlib import Path

from archlog.utils import get_datetime_now
from archlog.path_manager import PathManager


DEFAULT_CONFIG_FILENAME = "config.json"
DEFAULT_CONFIG = {
    "architecture-wording": "Architecture",
    "webscraper-delay": 3000,
    "arch-repositories": [
        {"name": "extra", "enabled": True},
        {"name": "core", "enabled": True},
        {"name": "multilib", "enabled": True},
        {"name": "core-testing", "enabled": False},
        {"name": "extra-testing", "enabled": False},
        {"name": "multilib-testing", "enabled": False},
        {"name": "testing", "enabled": False},
        {"name": "gnome-unstable", "enabled": False},
        {"name": "kde-unstable", "enabled": False},
    ],
    "paths": {
        "config-dir": "~/.config/archlog",
        "changelog-dir": "~/archlog/changelog",
        "logs-dir": "~/.local/state/archlog/logs",
    },
}


class ConfigHandler:
    def __init__(self, logger, config_filename: str = DEFAULT_CONFIG_FILENAME) -> None:
        """Constructor method"""
        self.logger = logger

        default_path_manager = PathManager(DEFAULT_CONFIG["paths"])
        self.config_path = default_path_manager.get_config_path(config_filename)

        # Ensure directories exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        self.config = self.load_config()
        self.path_manager = PathManager(self.config.get("paths", {}))

        user_paths = self.config.get("paths", {})
        default_paths = DEFAULT_CONFIG["paths"]

        if any(user_paths.get(key) != default_paths[key] for key in default_paths):
            self.path_manager = PathManager(user_paths)
            self.config_path = self.path_manager.get_config_path(config_filename)

        self.changelog_filename = get_datetime_now("%Y-%m-%d-changelog.json")

        self.changelog_path = self.path_manager.get_changelog_path()
        self.changelog_path.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"[Info]: Config file:         {self.config_path}")
        self.logger.info(f"[Info]: Changelog directory: {self.changelog_path}")
        self.logger.info(f"[Info]: Logs directory:      {self.path_manager.get_logs_path()}")

    def load_config(self) -> Dict[str, Any]:
        """
        Loads the configuration from a JSON file.

        :raises FileNotFoundError: If the configuration file does not exist, logs an error and returns None.
        :return: The loaded configuration as a dictionary, or None if the file is not found.
        :rtype: Dict[str, Any]
        """
        if not self.config_path.exists():
            self.logger.debug(f"[Debug]: Config file not found → creating default: {self.config_path}")
            with open(self.config_path, "w", encoding="utf-8") as write_config_file:
                json.dump(DEFAULT_CONFIG, write_config_file, indent=2)

        try:
            with open(self.config_path, "r", encoding="utf-8") as read_config_file:
                return json.load(read_config_file)
        except Exception as ex:
            self.logger.error(f"[Error]: Failed to load config: {ex}")
            exit(1)
        return config

    def initialize_changelog_file(self):
        """
        Initializes the changelog file by removing any existing file with the same name.

        :return: None
        """
        if os.path.exists(self.changelog_path / self.changelog_filename):
            os.remove(self.changelog_path / self.changelog_filename)

    def write_changelog(
        self,
        package: List[NamedTuple],
        package_changelog: List[Tuple[str, str, str, str, str]],
    ) -> None:
        """Writes changelog data for a specific package to a JSON file.

        :param package: An object containing information about the package. It should at least have
                the attributes `package_name`, `current_version`, and `new_version`.
        :type package: List[NamedTuple]
        :param package_changelog: A list of changelog data entries. Each tuple consists of:
                                - changelog_message (str): The commit message.
                                - package_url (str): The URL of the commit.
                                - package_tag (str): The version tag.
                                - arch_package_name (str): The name of the Arch package.
                                - release_type (str): The type of release (e.g., "minor", "major", "arch").
        :type package_changelog: List[Tuple[str, str, str, str, str]]
        :return: None
        """
        if (self.changelog_path / self.changelog_filename).exists():
            try:
                with open(self.changelog_path / self.changelog_filename, "r") as json_read_file:
                    existing_data = json.load(json_read_file)
            except json.JSONDecodeError:
                existing_data = {"packages": [], "changelog": {}}
        else:
            existing_data = {"packages": [], "changelog": {}}

        if package.package_name not in existing_data["packages"]:
            existing_data["packages"].append(package.package_name)

        if package.package_name not in existing_data["changelog"]:
            existing_data["changelog"][package.package_name] = {
                "current version": package.current_version,
                "new version": package.new_version,
                "versions": [],
            }

        versions_dict = {}

        if package_changelog:
            for (
                changelog_message,
                package_url,
                package_tag,
                arch_package_name,
                release_type,
                compare_tags_url,
            ) in package_changelog:
                compare_tags_url_arch = ""
                compare_tags_url_origin = ""

                if package_tag not in versions_dict:
                    for package_temp in package_changelog:
                        if package_tag == package_temp[2]:
                            if compare_tags_url_arch and compare_tags_url_origin:
                                break

                            compare_url = package_temp[5]
                            if (
                                (package_temp[4] == "arch" or package_temp[4] == "minor")
                                and "archlinux.org" in compare_url
                                and not compare_tags_url_arch
                            ):
                                compare_tags_url_arch = compare_url
                            elif package_temp[4] == "major":
                                compare_tags_url_origin = compare_url

                    versions_dict[package_tag] = {
                        "release-type": ("major" if release_type == "arch" else release_type),
                        "compare-url-tags-arch": (compare_tags_url_arch),
                        "compare-url-tags-origin": (compare_tags_url_origin),
                        "changelog": {
                            "changelog Arch package": [],
                            "changelog origin package": [],
                        },
                    }

                    if release_type == "minor":
                        versions_dict[package_tag]["changelog"]["changelog origin package"].append(
                            "- Not applicable, minor release -"
                        )
                        versions_dict[package_tag]["compare-url-tags-origin"] = "- Not applicable, minor release -"
                    else:
                        major_exists = any(
                            release_type_check == "major" for _, _, _, _, release_type_check, _ in package_changelog
                        )

                        if not major_exists:
                            versions_dict[package_tag]["changelog"]["changelog origin package"].append(
                                "- ERROR: Couldn't find origin changelog. Check the logs for further information -"
                            )
                if arch_package_name == package.package_name and release_type != "major":
                    versions_dict[package_tag]["changelog"]["changelog Arch package"].append(
                        {"commit message": changelog_message, "commit URL": package_url}
                    )
                else:
                    versions_dict[package_tag]["changelog"]["changelog origin package"].append(
                        {"commit message": changelog_message, "commit URL": package_url}
                    )
        else:
            version_tag = package.current_version
            versions_dict[version_tag] = {
                "release-type": "unknown",
                "compare-url-tags-arch": "",
                "compare-url-tags-origin": "",
                "changelog": {
                    "changelog Arch package": [],
                    "changelog origin package": [],
                },
            }

        for (
            versionTag,
            changelog_data,
        ) in versions_dict.items():
            existing_data["changelog"][package.package_name]["versions"].append(
                {
                    "version-tag": versionTag,
                    "release-type": changelog_data["release-type"],
                    "compare-url-tags-arch": changelog_data["compare-url-tags-arch"],
                    "compare-url-tags-origin": changelog_data["compare-url-tags-origin"],
                    "changelog": changelog_data["changelog"],
                }
            )

        # Write the updated website file data back to the file
        with open(self.changelog_path / self.changelog_filename, "w", encoding="utf-8") as json_write_file:
            json.dump(existing_data, json_write_file, indent=4, ensure_ascii=False)
