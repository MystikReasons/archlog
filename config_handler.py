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
        self.dt_string = self.datetime_now.strftime("%d.%m.%Y")

        self.logs_path = os.path.join(self.dir_path, "logs", "")

        if not os.path.exists(self.logs_path):
            os.makedirs(self.logs_path)

        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            filename=self.logs_path + self.dt_string_logging,
            format="%(asctime)s %(message)s",
            filemode="w")
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

        # Output the logging also to the console
        stream = logging.StreamHandler()
        stream.setLevel(logging.INFO)
        streamformat = logging.Formatter("%(message)s")
        stream.setFormatter(streamformat)
        self.logger.addHandler(stream)

    def load_config(self) -> Optional[Dict[str, Any]]:
        try:
            with open(self.config_path, "r") as read_config_file:
                config = json.load(read_config_file)
        except FileNotFoundError:
            self.logger.error(f"ERROR: Config file {self.config_path} not found.")
            return None
        return config

    def write_changelog(self, package_changelog: List[Tuple[str, str]]):
        # Write the updated website file data back to the file
        with open(website_collection_path, "w") as write_file:
            json.dump(website_file_data, write_file, indent=4)