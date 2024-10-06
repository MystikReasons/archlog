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
                filemode="w")
        except (FileNotFoundError, PermissionError) as ex:
            print(f"Error setting up log file: {ex}")
            return

        try:
            self.logger = logging.getLogger()
            self.logger.setLevel(logging.DEBUG)

            # Output the logging also to the console
            stream = logging.StreamHandler()
            stream.setLevel(logging.DEBUG)
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

    def write_changelog(self, package, package_changelog: List[Tuple[str, str, str]]):
        changelog_filename=self.changelog_path + self.dt_string_changelog

        if os.path.exists(changelog_filename):
            with open(changelog_filename, "r") as json_read_file:
                try:
                    existing_data = json.load(json_read_file)
                except json.JSONDecodeError:
                    existing_data = {}
        else:
            existing_data = {}

        if package.package_name not in existing_data:
            existing_data[package.package_name] = {
                "current version": package.current_version,
                "new version": package.new_version,
                "versions": []
            }

        versions_dict = {}
        
        if package_changelog:
            for commit_message, commit_url, commit_tag in package_changelog:
                if commit_tag not in versions_dict:
                    versions_dict[commit_tag] = []
                
                versions_dict[commit_tag].append({
                    "commit message": commit_message,
                    "commit URL": commit_url
                })
        else:
            version_tag = package.current_version
            versions_dict[version_tag] = []
        
        for versionTag, changelog in versions_dict.items():
            existing_data[package.package_name]["versions"].append({
                "version-tag": versionTag,
                "changelog": changelog
            })

        # Write the updated website file data back to the file
        with open(changelog_filename, "w") as json_write_file:
            json.dump(existing_data, json_write_file, indent=4)