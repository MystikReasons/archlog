from typing import Optional, Dict, Any, List, Tuple, NamedTuple
import os
import logging
import json
from datetime import datetime

DEFAULT_CONFIG_FILE_NAME = "config.json"


class ConfigHandler:
    def __init__(self, config_path=DEFAULT_CONFIG_FILE_NAME) -> None:
        """Constructor method"""
        self.dir_path = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.dir_path, config_path)
        self.config = self.load_config()

        self.datetime_now = datetime.now()
        self.dt_string_logging = self.datetime_now.strftime("%d-%m-%Y_%H-%M-%S")
        self.dt_string_changelog = self.datetime_now.strftime("changelog-%d-%m-%Y.json")

        self.logs_path = os.path.join(self.dir_path, "logs", "")
        if not os.path.exists(self.logs_path):
            os.makedirs(self.logs_path)

        self.changelog_path = os.path.join(self.dir_path, "changelog", "")
        if not os.path.exists(self.changelog_path):
            os.makedirs(self.changelog_path)

        self.setup_logging()

    def setup_logging(self) -> None:
        """
        Sets up logging for the application by configuring file and console handlers.

        The function initializes logging to a file and outputs logs to the console.
        Handles potential errors during the setup, such as file access issues.

        :raises FileNotFoundError: If the log file path is invalid or cannot be found.
        :raises PermissionError: If there are insufficient permissions to create or write to the log file.
        :raises Exception: For any other errors encountered during logger setup.
        :return: None
        """
        try:
            logging.basicConfig(
                filename=self.logs_path + self.dt_string_logging,
                format="%(asctime)s %(message)s",
                filemode="w",
            )
        except (FileNotFoundError, PermissionError) as ex:
            print(f"Error setting up log file: {ex}")
            return None

        try:
            self.logger = logging.getLogger()
            self.logger.setLevel(logging.DEBUG)

            # Output the logging also to the console
            stream = logging.StreamHandler()
            stream.setLevel(logging.INFO)
            streamformat = logging.Formatter("%(message)s")
            stream.setFormatter(streamformat)

            self.logger.addHandler(stream)
        except Exception as ex:
            print(f"Error setting up logger: {ex}")
            return None

    def load_config(self) -> Optional[Dict[str, Any]]:
        """
        Loads the configuration from a JSON file.

        :raises FileNotFoundError: If the configuration file does not exist, logs an error and returns None.
        :return: The loaded configuration as a dictionary, or None if the file is not found.
        :rtype: Optional[Dict[str, Any]]
        """
        try:
            with open(self.config_path, "r") as read_config_file:
                config = json.load(read_config_file)
        except FileNotFoundError:
            self.logger.error(f"[Error]: Config file {self.config_path} not found.")
            return None
        return config

    def initialize_changelog_file(self):
        """
        Initializes the changelog file by removing any existing file with the same name.
        """
        changelog_filename = self.changelog_path + self.dt_string_changelog

        if os.path.exists(changelog_filename):
            os.remove(changelog_filename)

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
        changelog_filename = self.changelog_path + self.dt_string_changelog

        if os.path.exists(changelog_filename):
            with open(changelog_filename, "r") as json_read_file:
                try:
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
                if (
                    arch_package_name == package.package_name
                    and release_type != "major"
                ):
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

        # Write the updated website file data back to the file
        with open(changelog_filename, "w", encoding="utf-8") as json_write_file:
            json.dump(existing_data, json_write_file, indent=4, ensure_ascii=False)
