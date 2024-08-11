from typing import Optional, List, Tuple
from collections import namedtuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import subprocess
import requests

class PackageHandler:
    def __init__(self, logger, config) -> None:
        self.logger = logger
        self.config = config
        self.enabled_repositories = []
        self.PackageInfo = namedtuple('PackageInfo', [
            'package_name',
            'current_version',
            'new_version',
            'current_main',
            'new_main',
            'current_suffix',
            'new_suffix'
        ])

        # Get the enabled repositories from the config file
        for repository in self.config.config.get('arch-repositories'):
            if(repository.get('enabled')):
                self.enabled_repositories.append(repository.get('name'))

    def get_upgradable_packages(self) -> List[str]:
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
            return []
        except PermissionError:
            self.logger.error("Error: Permission denied. Are you sure you have the necessary permissions to run this command?")
            return []
        except Exception as ex:
            self.logger.error(f"An unexpected error occurred: {ex}")
            return []

    def split_package_information(self, packages: List[str]) -> List[namedtuple]:
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

            packages_restructured.append(self.PackageInfo(
                package_name,
                current_version,
                new_version,
                current_main,
                new_main,
                current_suffix,
                new_suffix
            ))

        return packages_restructured

    def get_package_changelog(self, package: List[namedtuple]) -> List[Tuple[str, str]]:
        # To determine the exact arch package-adress we need the architecture and repository
        #                         repository  architecture
        #                                 |    |
        # https://archlinux.org/packages/core/any/automake/
        package_architecture = self.get_package_architecture(package.package_name)
        package_repository = self.get_package_repository(self.enabled_repositories, package.package_name, package_architecture)
        # TODO: package_repository should not be an array anymore in the future
        arch_package_url = "https://archlinux.org/packages/" + package_repository[0] + "/" + package_architecture + "/" + package.package_name
        
        package_source_files_url = self.get_package_source_files_url(arch_package_url) # TODO: Check if return value is None
        
        if not package_source_files_url:
                return []

        ## TODO: Check if the source files (PKGBUILD, etc.) did receive some updates beside pkver, pkgrel, etc...

        # Check if there was a major release
        # Example: 1.16.5-2 -> 1.17.5-1
        if package.current_main != package.new_main:
            package_upstream_url = self.get_package_upstream_url(arch_package_url) # TODO: Check if return value is None

            # Check if upstream url contains kde.org
            if('kde.org' in package_upstream_url):
                # KDE tags look like this: v6.1.3 while Arch uses it like this 1-6.1.3-1
                current_version_altered = 'v' + package.current_main.replace('1:', '')
                new_version_altered = 'v' + package.new_main.replace('1:', '')

                package_changelog = self.compare_tags('https://invent.kde.org/plasma/' + package.package_name, 
                    current_version_altered, 
                    new_version_altered
                )

                if package_changelog:
                    return package_changelog 
        
        # Check if there was a minor release
        # Example: 1.16.5-2 -> 1.16.5-3
        if (package.current_main == package.new_main) and (package.current_suffix != package.new_suffix) and package_source_files_url:
            package_changelog = self.compare_tags(package_source_files_url, package.current_version, package.new_version)

            if not package_changelog:
                self.logger.info(f"No package changelog for package: {package.package_name} found.")
                return []
            else:
                return package_changelog
        
        #self.check_website_availabilty(package)

    def get_package_architecture(self, package_name: str) -> str:
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

    def get_package_repository(self, enabled_repositories: List[str], package_name: str, package_architecture: str) -> str:
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

    def get_package_upstream_url(self, url: str) -> Optional[str]:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        upstream_link = soup.find('th', string='Upstream URL:')
        self.logger.info(f"Upstream URL: {upstream_link}")

        if upstream_link:
            upstream_url = upstream_link.find_next_sibling('td').find('a').get('href')
            self.logger.info(f"Upstream URL: {upstream_url}")
            return upstream_url
        else:
            self.logger.error(f"ERROR: Couldn't find node 'Upstream URL:' on {url}")
            return None

    def get_package_source_files_url(self, url: str) -> Optional[str]:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        source_file_link = soup.find('a', string='Source Files')

        if source_file_link:
            source_file_url = source_file_link.get('href')
            self.logger.info(f"Arch 'Source Files' URL: {source_file_url}")
            return source_file_url
        else:
            self.logger.error(f"ERROR: Couldn't find node 'Source Files' on {url}")
            return None

    def compare_tags(self, source: str, current_tag: str, new_tag: str) -> List[Tuple[str, str]]:
        compare_tags_url = source + '/-/compare/' + current_tag + '...' + new_tag
        self.logger.info(f"Compare tags URL: {compare_tags_url}")
        response = requests.get(compare_tags_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        commits = soup.find_all('a', class_='commit-row-message')
        commit_messages = [commit.get_text(strip=True) for commit in commits]
        incomplete_commit_urls = [commit.get('href') for commit in commits]
        full_commit_urls = [urljoin(source, commit_url) for commit_url in incomplete_commit_urls]

        combined_info = zip(commit_messages, full_commit_urls)

        if combined_info:
            return combined_info
        else:
            return []

    def check_website_availabilty(self, url: str) -> bool:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                self.logger.info(f"Website: {url} is reachable")
                return True
            else:
                self.logger.info(f"Website: {url} returned status code {response.status_code}.")
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