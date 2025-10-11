from typing import Dict, Any, List, Tuple, NamedTuple
import json
import os
from copy import deepcopy
from pathlib import Path

from archlog.utils import get_datetime_now
from archlog.path_manager import PathManager


DEFAULT_CONFIG_FILENAME = "config.json"


class ConfigHandler:
    def __init__(self, logger, config_filename: str = DEFAULT_CONFIG_FILENAME) -> None:
        """Constructor method"""
        self.logger = logger

        self.default_config = self.load_default_config()

        default_path_manager = PathManager(self.default_config["paths"])
        self.config_path = default_path_manager.get_config_path(config_filename)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        self.config = self.load_config()

        user_paths = self.config.get("paths", {})
        self.path_manager = PathManager(user_paths)
        self.config_path = self.path_manager.get_config_path(config_filename)

        self.changelog_filename = self.path_manager.get_changelog_filename()
        self.changelog_path = self.path_manager.get_changelog_path()
        self.changelog_path.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"[Info]: Config file:         {self.config_path}")
        self.logger.info(f"[Info]: Changelog directory: {self.changelog_path}")
        self.logger.info(
            f"[Info]: Logs directory:      {self.path_manager.get_logs_path()}"
        )

    def load_default_config(self) -> Dict[str, Any]:
        """
        Loads the default configuration supplied with the package from a JSON file.

        :return: The loaded default configuration as a dictionary.
        :rtype: Dict[str, Any]
        """
        import importlib.resources as config_resources

        with (
            config_resources.files("archlog")
            .joinpath("_resources/config.json")
            .open("r", encoding="utf-8") as config
        ):
            return json.load(config)

    def load_config(self) -> Dict[str, Any]:
        """
        Loads the configuration from a JSON file.
        It also checks if there are new missing configuration values which exist in the default config
        but not in the user config. If it finds missing configuration values, it will add them to the
        user config file.

        :raises FileNotFoundError: If the configuration file does not exist, logs an error and returns None.
        :return: The loaded configuration as a dictionary, or None if the file is not found.
        :rtype: Dict[str, Any]
        """
        if not self.config_path.exists():
            self.logger.debug(
                f"[Debug]: Config file not found -> creating default: {self.config_path}"
            )
            with open(self.config_path, "w", encoding="utf-8") as write_config_file:
                json.dump(self.default_config, write_config_file, indent=2)

        try:
            with open(self.config_path, "r", encoding="utf-8") as read_config_file:
                user_config = json.load(read_config_file)
        except Exception as ex:
            self.logger.error(f"[Error]: Failed to load config: {ex}")
            exit(1)

        # Check if the default config file has new entries which the current user config file does not have
        if self.merge_config(self.default_config, user_config):
            self.logger.info(
                f"[Info]: Adding missing config values from default config file."
            )
            with open(self.config_path, "w", encoding="utf-8") as write_config_file:
                json.dump(user_config, write_config_file, indent=2)

        return user_config

    def initialize_changelog_file(self):
        """
        Initializes the changelog file by removing any existing file with the same name.

        :return: None
        """
        if os.path.exists(self.changelog_path / self.changelog_filename):
            os.remove(self.changelog_path / self.changelog_filename)

    def merge_config(
        self, default_config: Dict[str, Any], user_config: Dict[str, Any]
    ) -> bool:
        """
        Recursively adds missing keys from the default configuration into the user configuration.

        :param default_config: The complete default configuration
        :param user_config: The loaded user configuration
        :return: True if any values were added or changed
        """
        updated = False
        new_user_config = {}

        for key, value in default_config.items():
            if key in user_config:
                # Key exists -> keep it, merge recursively if both are dicts
                if isinstance(value, dict) and isinstance(user_config[key], dict):
                    if self.merge_config(value, user_config[key]):
                        updated = True
                new_user_config[key] = user_config[key]
            else:
                # Key is missing -> insert at the position of default_config
                new_user_config[key] = deepcopy(value)
                updated = True

        user_config.clear()
        user_config.update(new_user_config)

        return updated

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
                with open(
                    self.changelog_path / self.changelog_filename, "r"
                ) as json_read_file:
                    existing_data = json.load(json_read_file)
            except json.JSONDecodeError:
                existing_data = {"packages": [], "changelog": {}}
        else:
            existing_data = {"packages": [], "changelog": {}}

        if package.package_name not in existing_data["packages"]:
            existing_data["packages"].append(package.package_name)

        if package.package_name not in existing_data["changelog"]:
            existing_data["changelog"][package.package_name] = {
                "description": package.package_description,
                "base package": package.package_base if package.package_base else "-",
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
                                (
                                    package_temp[4] == "arch"
                                    or package_temp[4] == "minor"
                                )
                                and "archlinux.org" in compare_url
                                and not compare_tags_url_arch
                            ):
                                compare_tags_url_arch = compare_url
                            elif package_temp[4] == "major":
                                compare_tags_url_origin = compare_url

                    versions_dict[package_tag] = {
                        "release-type": (
                            "major" if release_type == "arch" else release_type
                        ),
                        "compare-url-tags-arch": (compare_tags_url_arch),
                        "compare-url-tags-origin": (compare_tags_url_origin),
                        "changelog": {
                            "changelog Arch package": [],
                            "changelog origin package": [],
                        },
                    }

                    if release_type == "minor":
                        versions_dict[package_tag]["changelog"][
                            "changelog origin package"
                        ].append("- Not applicable, minor release -")
                        versions_dict[package_tag][
                            "compare-url-tags-origin"
                        ] = "- Not applicable, minor release -"
                    else:
                        major_exists = any(
                            release_type_check == "major"
                            for _, _, _, _, release_type_check, _ in package_changelog
                        )

                        if not major_exists:
                            versions_dict[package_tag]["changelog"][
                                "changelog origin package"
                            ].append(
                                "- ERROR: Couldn't find origin changelog. Check the logs for further information -"
                            )
                if release_type != "major":
                    versions_dict[package_tag]["changelog"][
                        "changelog Arch package"
                    ].append(
                        {"commit message": changelog_message, "commit URL": package_url}
                    )
                else:
                    versions_dict[package_tag]["changelog"][
                        "changelog origin package"
                    ].append(
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
                    "compare-url-tags-origin": changelog_data[
                        "compare-url-tags-origin"
                    ],
                    "changelog": changelog_data["changelog"],
                }
            )

        # Write the updated changelog file data back to the file
        with open(
            self.changelog_path / self.changelog_filename, "w", encoding="utf-8"
        ) as json_write_file:
            json.dump(existing_data, json_write_file, indent=4, ensure_ascii=False)
