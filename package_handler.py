from typing import Optional, List, Tuple
from collections import namedtuple
from urllib.parse import urljoin
from web_scraper import WebScraper
import subprocess
import requests

class PackageHandler:
    def __init__(self, logger, config) -> None:
        self.web_scraper = WebScraper()
        self.logger = logger
        self.config = config
        self.enabled_repositories = []
        self.PackageInfo = namedtuple('PackageInfo', [
            'package_name',
            'current_version',
            'current_version_altered',
            'new_version',
            'new_version_altered',
            'current_main',
            'current_main_altered',
            'new_main',
            'current_suffix',
            'new_suffix'
        ])

        # Get the enabled repositories from the config file
        for repository in self.config.config.get('arch-repositories'):
            if(repository.get('enabled')):
                self.enabled_repositories.append(repository.get('name'))

    def get_upgradable_packages(self) -> List[str]:
        """
        This function gets via `pacman` all the upgradable packages on the local system.
        It uses first `pacman -Sy` and after that `pacman -Qu`. This will first update the local mirror
        with the server mirror and then print out all upgradable packages.

        :return: A list of upgradable packages with the following structure.
        :rtype: List[str]

        :raises subprocess.CalledProcessError: If the `pacman` commands return a non-zero exit status.
            This includes errors like network issues.
        :raises PermissionError: If there is a permissions issue when trying to execute `sudo` commands.
            This could occur if the user does not have the necessary permissions to run `sudo` or the `pacman` commands.
        :raises Exception: For any other unexpected errors that occur during execution.
        """
        try:
            # Update the local mirror
            update_process = subprocess.run(
                ["sudo", "pacman", "-Sy"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, # This will prevent the output from doing this: "b'PACKAGE"
                check=True) # This will raise an exception if the command fails

            # Get the list of upgradable packages
            process = subprocess.run(
                ["sudo", "pacman", "-Qu"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, # This will prevent the output from doing this: "b'PACKAGE"
                check=True) # This will raise an exception if the command fails

            packages_to_update = process.stdout.splitlines()
            packages_to_update = self.split_package_information(packages_to_update)
            return packages_to_update
        except subprocess.CalledProcessError as ex:
            self.logger.error(f"ERROR: Command '{ex.cmd}' returned non-zero exit status {ex.returncode}.")
            self.logger.error("Standard Error:")
            self.logger.error(ex.stderr)
            return None
        except PermissionError:
            self.logger.error("ERROR: Permission denied. Are you sure you have the necessary permissions to run this command?")
            return None
        except Exception as ex:
            self.logger.error(f"ERROR: An unexpected error occurred: {ex}")
            return None

    def split_package_information(self, packages: List[str]) -> List[namedtuple]:
        """
        Splits package information into a list of namedtuples with detailed version information.

        :param packages: A list of strings, where each string contains a package name
                         followed by the current version and new version information.
        :type packages: List[str]

        :return: A list of namedTuples. Each namedtuple contains:
            - package_name (str): The name of the package
            - current_version (str): The current version of the package.
            - current_version_altered (str): The altered version of the current version (colon `:` replaced by hyphen `-`).
            - new_version (str): The new version of the package.
            - new_version_altered (str): The altered version of the new version (colon `:` replaced by hyphen `-`).
            - current_main (str): The main part of the current version (before the hyphen).
            - current_main_altered (str): The altered main part of the current version.
            - new_main (str): The main part of the new version (before the hyphen).
            - current_suffix (str): The suffix of the current version (after the hyphen).
            - new_suffix (str): The suffix of the new version (after the hyphen).
        :rtype: List[namedtuple(
                    PackageInfo, 
                    ['package_name', 'current_version', 'current_version_altered',
                    'new_version', 'new_version_altered', 'current_main', 
                    'current_main_altered', 'new_main', 'current_suffix', 'new_suffix']
                )]
        """
        packages_restructured = []

        # Example: automake 1.16.5-2 -> 1.17-1
        for line in packages:
            parts = line.split(' ')
            package_name            = parts[0]
            current_version         = parts[1]
            # Some Arch packages do have versions that look like this: 1:1.16.5-2
            # On their repository host (Gitlab) the tags do like this: 1-1.16.5-2
            # To prevent repetitive code which replaces the symbol, we do it here
            current_version_altered = current_version.replace('1:', '1-')
            new_version             = parts[3]
            new_version_altered     = new_version.replace('1:', '1-')
            current_main            = parts[1].split('-')[0]
            current_main_altered    = current_main.replace('1:', '1-')
            new_main                = parts[3].split('-')[0]
            current_suffix          = parts[1].split('-')[1]
            new_suffix              = parts[3].split('-')[1]

            packages_restructured.append(self.PackageInfo(
                package_name,
                current_version,
                current_version_altered,
                new_version,
                new_version_altered,
                current_main,
                current_main_altered,
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

        if not package_architecture:
            return None

        package_repository = self.get_package_repository(self.enabled_repositories, package.package_name, package_architecture)
        # TODO: package_repository should not be an array anymore in the future
        arch_package_url = "https://archlinux.org/packages/" + package_repository[0] + "/" + package_architecture + "/" + package.package_name
        if (not package_source_files_url):
            return None

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
            # Some Arch packages do have versions that look like this: 1:1.16.5-2
            # On their repository host (Gitlab) the tags do like this: 1-1.16.5-2
            # In order to make a tag compare on Gitlab, use the altered versions
            package_changelog = self.get_changelog(package_source_files_url,
                                                   package.current_version_altered,
                                                   package.new_version_altered)

            if not package_changelog:
                self.logger.info(f"No package changelog for package: {package.package_name} found.")
                return []
            else:
                return package_changelog
        
        #self.check_website_availabilty(package)

    def get_package_architecture(self, package_name: str) -> str:
        """
        Retrieves the architecture of a specified package using `pacman`.

        This function runs `sudo pacman -Q --info <package_name>` to obtain information about the
        package, then parses the output to extract the architecture of the package.

        :param str package_name: The name of the upgradable package whose architecture should be retrieved.

        :return: The architecture of the specified package.
        :rtype: str

        :raises subprocess.CalledProcessError: If the `pacman` command returns a non-zero exit status.
            This may occur if the package name is incorrect or if there is an issue executing the command.
        :raises PermissionError: If there is a permissions issue when trying to execute the `pacman` command.
            This could occur if the user does not have the necessary permissions to run the command.
        :raises Exception: For any other unexpected errors that occur during execution.
        """
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
        """
        Determines the repository from which a specified package can be retrieved.

        This function checks the availability of the specified package in each of the enabled repositories.
        It constructs URLs for each repository based on the package name and architecture, and verifies
        their reachability. If multiple repositories are found to be reachable, an error is logged, as the
        user should configure either stable or testing repositories exclusively.

        :param List[str] enabled_repositories: A list of enabled repository names to check (from config file).
        :param str package_name: The name of the package to check.
        :param str package_architecture: The architecture of the package (e.g., 'x86_64').

        :return: The name of the reachable repository if exactly one is found; otherwise, an error is logged and the program exits.
        :rtype: str

        :raises Exception: If multiple reachable repositories are found, indicating a configuration issue.
        """
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
        response = self.web_scraper.fetch_page_content(url)
        if response is None:
            return None

        upstream_link = self.web_scraper.find_element(response, 'th', string='Upstream URL:')
        if upstream_link:
            upstream_url = upstream_link.find_next_sibling('td').find('a').get('href')
            self.logger.info(f"Upstream URL: {upstream_url}")
            return upstream_url
        else:
            self.logger.error(f"ERROR: Couldn't find node 'Upstream URL:' on {url}")
            return None

    def get_package_source_files_url(self, url: str) -> Optional[str]:
        """
        Retrieves the URL for the source files of a package from a webpage.

        This function sends an HTTP GET request to the specified URL, parses the HTML content to find a link with the
        text 'Source Files', and returns the URL of that link. If the 'Source Files' link is not found, the function
        returns `None`.

        :param str url: The URL of the webpage to retrieve and parse.

        :return: The URL of the 'Source Files' link if found, or `None` if the link is not found.
        :rtype: Optional[str]

        :raises requests.RequestException: If an error occurs during the HTTP request.
            This includes network errors, invalid URLs, or issues with the request itself.
        :raises Exception: For any other unexpected errors that occur during HTML parsing.
        """
        try:
            response = self.web_scraper.fetch_page_content(url)
            if response is None:
                return None

            source_file_link = self.web_scraper.find_element(response, 'a', string='Source Files')

            if source_file_link:
                source_file_url = source_file_link.get('href')
                self.logger.info(f"Arch 'Source Files' URL: {source_file_url}")
                return source_file_url
            else:
                self.logger.error(f"ERROR: Couldn't find node 'Source Files' on {url}")
                return None
        except requests.RequestException as ex:
            self.logger.error(f"ERROR: An error occurred during the HTTP request to {url}. Error code: {ex}")
            return None
        except Exception as ex:
            self.logger.error(f"ERROR: An unexpected error occurred while parsing the HTML: {ex}")
            return None
        compare_tags_url = source + '/-/compare/' + current_tag + '...' + new_tag
        self.logger.debug(f"Compare tags URL: {compare_tags_url}")

        response = self.web_scraper.fetch_page_content(compare_tags_url)
        commits = self.web_scraper.find_all_elements(response, 'a', class_='commit-row-message')
        if not commits:
            self.logger.debug(f"No commit messages found in the response from {compare_tags_url}")
            return None

        commit_messages = [commit.get_text(strip=True) for commit in commits]
        incomplete_commit_urls = [commit.get('href') for commit in commits]
        full_commit_urls = [urljoin(source, commit_url) for commit_url in incomplete_commit_urls]

        combined_info = zip(commit_messages, full_commit_urls)

        if combined_info:
            return combined_info
        else:
            return None

    def check_website_availabilty(self, url: str) -> bool:
        """
        Checks the availability of a website by sending an HTTP GET request.

        This function sends a GET request to the specified URL and checks the HTTP status code of the response.
        If the status code is 200, it indicates that the website is reachable. Any other status code indicates
        that the website may be down or returning an error.

        :param str url: The URL of the website to check.

        :return: True if the website is reachable (status code 200), otherwise False.
        :rtype: bool

        :raises requests.RequestException: If an error occurs during the HTTP request.
            This includes network errors, invalid URLs, or issues with the request itself.
        """
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