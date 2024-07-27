#! /usr/bin/python3
from bs4 import BeautifulSoup
import json
import logging
import os
import sys
import sh
import requests
import subprocess
from datetime import datetime

DEFAULT_CONFIG_FILE_NAME = "config.json"

class ConfigHandler:
    def __init__(self, config_path=DEFAULT_CONFIG_FILE_NAME):
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

    def load_config(self):
        try:
            with open(self.config_path, "r") as read_config_file:
                config = json.load(read_config_file)
        except FileNotFoundError:
            self.logger.error(f"ERROR: Config file {self.config_path} not found.")
            return False
        return config

class PackageHandler:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.enabled_repositories = []

        # Get the enabled repositories from the config file
        for repository in self.config.config.get('arch-repositories'):
            if(repository.get('enabled')):
                self.enabled_repositories.append(repository.get('name'))

    def get_upgradable_packages(self):
        try:
            update_process = subprocess.run(
                ["sudo", "pacman", "-Sy"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)

            process = subprocess.run(
                ["sudo", "pacman", "-Qu"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True) # use text=True to prevent it from doing this: "b'PACKAGE"

            packages_to_update = process.stdout.splitlines()
            packages_to_update = self.split_package_information(packages_to_update)
            return packages_to_update

        except subprocess.CalledProcessError as ex:
            self.logger.error(f"Error: Command '{ex.cmd}' returned non-zero exit status {ex.returncode}.")
            self.logger.error("Standard Error:")
            self.logger.error(e.stderr)
        except PermissionError:
            self.logger.error("Error: Permission denied. Are you sure you have the necessary permissions to run this command?")
        except Exception as ex:
            self.logger.error(f"An unexpected error occurred: {ex}")

    def split_package_information(self, packages):
        packages_restructured = []

        # Example: automake 1.16.5-2 -> 1.17-1
        for line in packages:
            parts = line.split(' ')
            package_name    = parts[0]
            current_version = parts[1]
            new_version     = parts[3]
            current_main    = parts[1].split('-')[0]
            new_main        = parts[3].split('-')[0]
            current_suffix  = parts[1].split('-')[1]
            new_suffix      = parts[3].split('-')[1]

            packages_restructured.append((package_name,
                                        current_version,
                                        new_version,
                                        current_main,
                                        new_main,
                                        current_suffix,
                                        new_suffix))

        return packages_restructured

    def get_package_changelog(self, package):
        # To determine the exact arch package-adress we need the architecture and repository
        #                         repository  architecture
        #                                 |    |
        # https://archlinux.org/packages/core/any/automake/
        package_architecture = self.get_package_architecture(package[0])
        package_repository = self.get_package_repository(self.enabled_repositories, package[0], package_architecture)

        #self.check_website_availabilty(package)

    def get_package_architecture(self, package_name):
        try:
            result = subprocess.run(
                ['pacman', '-Q', '--info', package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True)

        except subprocess.CalledProcessError as ex:
            self.logger.error(f"Error: Command '{ex.cmd}' returned non-zero exit status {ex.returncode}.")
            self.logger.error("Standard Error:")
            self.logger.error(e.stderr)
            exit(1)
        except PermissionError:
            self.logger.error("Error: Permission denied. Are you sure you have the necessary permissions to run this command?")
            exit(1)
        except Exception as ex:
            self.logger.error(f"An unexpected error occurred: {ex}")
            exit(1)

        output = result.stdout.splitlines()

        for line in output:
            if line.startswith('Architektur'): # TODO: Currently language-dependent
                package_architecture = line.split(':')[1].strip()
                self.logger.info(f"Package architecture: {package_architecture}")

        return package_architecture

    def get_package_repository(self, enabled_repositories, package_name, package_architecture):
        reachable_repository = []
        for repository in enabled_repositories:
            possible_url = "https://archlinux.org/packages/" + repository + "/" + package_architecture + "/" + package_name
            
            if(self.check_website_availabilty(possible_url)):
                reachable_repository.append(repository)

        # Multiple repositories from Arch do contain the same package.
        # The versions could be the same but could also differ.
        # This is an error of the user and he should either enable the stable
        # repositories or the testing in the config file.
        if len(reachable_repository) > 1:
            self.logger.error("ERROR: Multiple repositories found. Please use either stable or testing in the config file.")
            exit(1)
        else:
            return reachable_repository

    def check_website_availabilty(self, url):
        self.logger.info("Checking website availabilty")
        try:
            response = requests.get(url)
            if response.status_code == 200:
                self.logger.info(f"Website {url} is reachable")
                return True
            else:
                self.logger.info(f"Website {url} returned status code {response.status_code}.")
                return False
        except requests.RequestException as ex:
            self.logger.error(f"ERROR: An error occured during checking availability of website {url}. Error code: {ex}")
            return False

    def arch(self):
        self.logger.info("Checking Arch website changelog")

    def gitlab(self):
        self.logger.info("Checking Gitlab changelog")

    def github(self):
        self.logger.info("Checking Github changelog")

    def upstream(self):
        self.logger.info("Checking upstream changelog")

def main():
    config_handler = ConfigHandler()
    logger = config_handler.logger
    package_handler = PackageHandler(logger, config_handler)

    print("Package Changelog Viewer")
    print("------------------------")
    logger.info("Logger is set up")

    packages_to_update = package_handler.get_upgradable_packages()

    if not packages_to_update:
        logger.info("No packages to upgrade")
        exit()

    logger.info(f"Upgradable packages ({len(packages_to_update)}):")
    logger.info("--------------------")
    for package in packages_to_update:
        print(f"{package[0]} {package[1]} -> {package[2]}")
        package_handler.get_package_changelog(package)

if __name__ == "__main__":
    main()
