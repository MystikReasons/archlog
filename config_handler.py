from typing import Optional, Dict, Any, List, Tuple
import os
import logging
import json
from datetime import datetime

DEFAULT_CONFIG_FILE_NAME = "config.json"


class ConfigHandler:
    def __init__(self, config_path=DEFAULT_CONFIG_FILE_NAME) -> None:
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

    def setup_logging(self):
        try:
            logging.basicConfig(
                filename=self.logs_path + self.dt_string_logging,
                format="%(asctime)s %(message)s",
                filemode="w",
            )
        except (FileNotFoundError, PermissionError) as ex:
            print(f"Error setting up log file: {ex}")
            return

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
            return

    def load_config(self) -> Optional[Dict[str, Any]]:
        try:
            with open(self.config_path, "r") as read_config_file:
                config = json.load(read_config_file)
        except FileNotFoundError:
            self.logger.error(f"ERROR: Config file {self.config_path} not found.")
            return None
        return config

    def initialize_changelog_file(self):
        changelog_filename = self.changelog_path + self.dt_string_changelog

        if os.path.exists(changelog_filename):
            os.remove(changelog_filename)

    def write_changelog(
        self, package, package_changelog: List[Tuple[str, str, str, str, str]]
    ):
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
            major_changelog_found = False

            for (
                changelog_message,
                package_url,
                package_tag,
                arch_package_name,
                release_type,
            ) in package_changelog:
                if package_tag not in versions_dict:
                    versions_dict[package_tag] = {
                        "release-type": (
                            "major" if release_type == "arch" else release_type
                        ),
                        "changelog": {
                            "changelog Arch package": [],
                            "changelog origin package": [],
                        },
                    }

                    if release_type == "minor":
                        versions_dict[package_tag]["changelog"][
                            "changelog origin package"
                        ].append("- Not applicable, minor release -")

                    if release_type != "minor" and not major_changelog_found:
                        major_exists = any(
                            release_type_check == "major"
                            for _, _, _, _, release_type_check in package_changelog
                        )

                        if not major_exists:
                            versions_dict[package_tag]["changelog"][
                                "changelog origin package"
                            ].append(
                                "- ERROR: Couldn't find origin changelog. Check the logs for further information -"
                            )
                            major_changelog_found = True

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
                "changelog": {
                    "changelog Arch package": [],
                    "changelog origin package": [],
                },
            }

        for versionTag, changelog_data in versions_dict.items():
            existing_data["changelog"][package.package_name]["versions"].append(
                {
                    "version-tag": versionTag,
                    "release-type": changelog_data["release-type"],
                    "changelog": changelog_data["changelog"],
                }
            )

        # Write the updated website file data back to the file
        with open(changelog_filename, "w") as json_write_file:
            json.dump(existing_data, json_write_file, indent=4)
