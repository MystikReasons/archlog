from typing import Optional, List, Tuple, Dict, Any
from collections import namedtuple
from urllib.parse import urljoin, urlparse
import re
import subprocess
import shutil
from difflib import SequenceMatcher
from rapidfuzz import process
import tomllib

from archlog.web_scraper import WebScraper
from archlog.apis.gitlab_api import GitLabAPI
from archlog.apis.archlinux_api import ArchLinuxAPI


class PackageHandler:
    """Initializes an instance of the class with the necessary configuration and logger.
    Sets up the web scraper, logger, and loads the enabled repositories from the configuration.

    :param logger: Logger object for logging messages.
    :type logger: Logger
    :param config: Configuration object containing all required settings.
    :type config: Config
    """

    def __init__(self, logger, config: Optional[Dict[str, Any]]) -> None:
        """Constructor method"""
        self.logger = logger
        self.config = config
        self.web_scraper = WebScraper(self.logger, self.config)
        self.gitlab_api = GitLabAPI(self.logger)
        self.archlinux_api = ArchLinuxAPI(self.logger)
        self.enabled_repositories = []
        self.PackageInfo = namedtuple(
            "PackageInfo",
            [
                "package_name",
                "current_version",
                "current_version_altered",
                "new_version",
                "new_version_altered",
                "current_main",
                "current_main_altered",
                "new_main",
                "current_suffix",
                "new_suffix",
            ],
        )

        # Get the enabled repositories from the config file
        arch_repositories = self.config.config.get("arch-repositories", [])
        for repository in arch_repositories:
            if repository.get("enabled"):
                self.enabled_repositories.append(repository.get("name"))

        # Ensures that if already a changelog file from today exists, delete it
        self.config.initialize_changelog_file()

    def get_upgradable_packages(self) -> Optional[List[str]]:
        """This function gets via `pacman` all the upgradable packages on the local system.
        It uses first `pacman -Sy` and after that `pacman -Qu`. This will first update the local mirror
        with the server mirror and then print out all upgradable packages.

        :raises subprocess.CalledProcessError: If the command returns a non-zero exit status.
        :raises PermissionError: If the command cannot be executed due to insufficient permissions.
        :raises Exception: For any unexpected errors.
        :raises SystemExit: Always called if any exception is encountered, terminating the program.
        :return: A list of upgradable package names. Each entry in the list is a string.
        :rtype: List[str]
        """
        if shutil.which("checkupdates") is None:
            self.logger.error(
                f(
                    """[Error]: Command 'checkupdates' is not available. 
                Install the package 'pacman-contrib' to use this program."""
                )
            )
            exit(1)
        else:
            try:
                # Get the list of upgradable packages
                update_process = subprocess.run(
                    ["checkupdates"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,  # This will prevent the output from doing this: "b'PACKAGE"
                )

                packages_to_update = update_process.stdout.splitlines()
                packages_to_update = self.split_package_information(packages_to_update)
                return packages_to_update
            except subprocess.CalledProcessError as ex:
                self.logger.error(f"[Error]: Command '{ex.cmd}' returned non-zero exit status {ex.returncode}.")
                self.logger.error("[Error]: Standard Error:")
                self.logger.error(ex.stderr)
                exit(1)
            except PermissionError:
                self.logger.error(
                    "[Error]: Permission denied. Are you sure you have the necessary permissions to run this command?"
                )
                exit(1)
            except Exception as ex:
                self.logger.error(f"[Error]: An unexpected error occurred: {ex}")
                exit(1)

    def split_package_information(self, packages: List[str]) -> List[namedtuple]:
        """Splits package information into a list of namedtuples with detailed version information.

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
            replacements = {"1:": "1-", "2:": "2-", "3:": "3-"}
            parts = line.split(" ")
            package_name = parts[0]
            current_version = parts[1]
            new_version = parts[3]
            current_main = parts[1].split("-")[0]
            new_main = parts[3].split("-")[0]
            current_suffix = parts[1].split("-")[1]
            new_suffix = parts[3].split("-")[1]

            new_version_altered = new_version
            current_version_altered = current_version
            current_main_altered = current_main

            # Some Arch packages do have versions that look like this: 1:1.16.5-2
            # On their repository host (Gitlab) the tags do like this: 1-1.16.5-2
            # To prevent repetitive code which replaces the symbol, we do it here
            for old, new in replacements.items():
                new_version_altered = new_version_altered.replace(old, new)
                current_version_altered = current_version_altered.replace(old, new)
                current_main_altered = current_main_altered.replace(old, new)

            packages_restructured.append(
                self.PackageInfo(
                    package_name,
                    current_version,
                    current_version_altered,
                    new_version,
                    new_version_altered,
                    current_main,
                    current_main_altered,
                    new_main,
                    current_suffix,
                    new_suffix,
                )
            )

        return packages_restructured

    def split_package_tag(self, tag: str) -> tuple[str, str]:
        """
        Splits a package tag into its main part and suffix.

        The function determines the number of parts in the tag based on the occurrences of "-".
        Depending on the tag format, it assigns the main and suffix parts accordingly.

        Examples:
            - "1-15.2.3-2" -> ("15.2.3", "1")
            - "24.12.2-1" -> ("24.12.2", "1")

        :param tag: The package tag to be split.
        :type tag: str
        :return: A tuple containing the main part of the tag and the suffix.
        :rtype: tuple[str, str]
        """
        # Add + 1 because if there are at least two "-", it's always one part more
        tag_parts_count = tag.count("-") + 1
        tag_parts = tag.split("-")[:tag_parts_count]

        # Differentiate the different tag styles
        # Example: 1-15.2.3-2, 24.12.2-1
        if tag_parts_count >= 3:
            tag_part_suffix = tag_parts[0]
            tag_part_main = tag_parts[1]
        else:
            if len(tag_parts[0]) < len(tag_parts[1]):
                tag_part_suffix = tag_parts[0]
                tag_part_main = tag_parts[1]
            else:
                tag_part_suffix = tag_parts[1]
                tag_part_main = tag_parts[0]

        return tag_part_main, tag_part_suffix

    def get_package_changelog(self, package: namedtuple) -> Optional[List[Tuple[str, str, str, str, str]]]:
        """Generates a changelog for a specified package by analyzing intermediate, minor, and major releases
        between its current and new versions. It fetches and compares relevant metadata and tags from
        Arch Linux repositories, as well as upstream sources like GitHub, GitLab, and KDE GitLab.

        :param package: A named tuple containing the package information, such as the package name,
                        current version, new version, main version tags, and suffixes.
        :type package: namedtuple
        :return: A list of tuples containing changelog information for the package. Each tuple provides
                details on each relevant change from intermediate, major, and minor versions, in the format:
                (tag, date, version, description, change type).
        :rtype: Optional[List[Tuple[str, str, str, str, str]]]
        """
        package_changelog = []

        # To determine the exact arch package-adress we need the architecture and repository
        #                         repository  architecture
        #                                 |    |
        # https://archlinux.org/packages/core/any/automake/
        package_architecture = self.get_package_architecture(package.package_name)

        arch_package_repository = self.get_package_repository(
            self.enabled_repositories, package.package_name, package_architecture
        )

        if not arch_package_repository:
            return None

        # TODO: package_repository should not be an array anymore in the future
        arch_package_url = (
            "https://archlinux.org/packages/"
            + arch_package_repository[0]
            + "/"
            + package_architecture
            + "/"
            + package.package_name
        )

        arch_package_overview_information = self.archlinux_api.get_package_overview_site_information(
            package.package_name
        )

        if not all(arch_package_overview_information):
            self.logger.error(f"[Error]: Couldn't extract all required information from {arch_package_url}.")
            return None

        package_upstream_url_overview = arch_package_overview_information[0]
        package_base = arch_package_overview_information[1]  # For example bluez-libs is based on bluez
        package_name_search = package.package_name if not package_base else package_base

        package_source_files_url = self.archlinux_api.get_gitlab_package_url(package_name_search)

        self.logger.info(f"[Info]: Arch 'Source Files' URL: {package_source_files_url}")

        # Check if there were multiple releases on Arch side (either major or minor)
        # This will check the current local version with the first intermediate tag and then it will shift.
        # Example: current version -> 1st intermediate version (minor) -> 2nd intermediate version (major) -> ...
        # 1st iteration: current version -> 1st intermediate version (minor)
        # 2nd iteration: 1st intermediate version (minor) -> 2nd intermediate version (major)
        arch_package_tags = self.get_package_tags(
            package_source_files_url + "/-/tags",
            self.gitlab_api.base_urls["Arch"],
            "archlinux/packaging/packages/" + package_name_search,
        )

        if not arch_package_tags:
            self.logger.error(f"[Error]: {package.package_name}: Couldn't find any arch package tags")
            return None

        # Try to get the content of the .nvchecker.toml file, if existing
        # This will be used instead of the package_upstream_url_overview since this mostly does not contain the
        # correct URL regarding the git package hosting website.
        # Example for xorg-server:
        # package_upstream_url_overview: https://xorg.freedesktop.org
        # .nvchecker.toml url: https://gitlab.freedesktop.org/xorg/xserver/-/tags
        # https://gitlab.archlinux.org/archlinux/packaging/packages/xorg-server/-/blob/main/.nvchecker.toml?ref_type=heads
        nvchecker_content = self.gitlab_api.get_file_content(
            self.gitlab_api.base_urls["Arch"], "archlinux/packaging/packages/" + package_name_search, ".nvchecker.toml"
        )

        package_upstream_url_nvchecker = None
        if nvchecker_content:
            parsed_content = tomllib.loads(nvchecker_content)
            if parsed_content[package_name_search].get("url"):
                package_upstream_url_nvchecker = parsed_content[package_name_search]["url"]
            elif parsed_content[package_name_search].get("git"):
                package_upstream_url_nvchecker = parsed_content[package_name_search]["git"]

                if ".git" in package_upstream_url_nvchecker:
                    package_upstream_url_nvchecker = package_upstream_url_nvchecker.removesuffix(".git")
            else:
                self.logger.debug(
                    f"[Debug]: {package.package_name}: Found no URL in .nvchecker.toml in {package_source_files_url}."
                )
        else:
            self.logger.debug(
                f"[Debug]: {package.package_name}: Found no .nvchecker.toml file in {package_source_files_url}."
            )

        intermediate_tags = self.find_intermediate_tags(arch_package_tags, package.current_version, package.new_version)
        if intermediate_tags:
            self.logger.info(f"[Info]: Intermediate tags: {intermediate_tags}")
            package_changelog_temp = self.handle_intermediate_tags(
                intermediate_tags,
                package,
                package_name_search,
                package_source_files_url,
                package_upstream_url_nvchecker if package_upstream_url_nvchecker else package_upstream_url_overview,
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

            if package_changelog:
                return package_changelog
            else:
                return None
        else:
            self.logger.info("[Info]: No intermediate tags found")

        # Check if there was a major release
        # Example: 1.16.5-2 -> 1.17.5-1
        if package.current_main != package.new_main:
            self.logger.info(f"[Info]: {package.new_version} is a major release")

            # Always get the Arch package changelog too, which is the same as the "minor" release case
            package_changelog_temp = self.get_changelog_compare_package_tags(
                package_source_files_url,
                package.current_version_altered,
                package.new_version_altered,
                package_name_search,
                "arch",
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

            package_changelog_temp = self.get_package_changelog_upstream_source(
                package_upstream_url_nvchecker if package_upstream_url_nvchecker else package_upstream_url_overview,
                package_source_files_url,
                package,
                package.current_version_altered,
                package.new_version_altered,
                package_name_search,
                package.new_version_altered,
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

        # Check if there was a minor release
        # Example: 1.16.5-2 -> 1.16.5-3
        if (
            (package.current_main == package.new_main)
            and (package.current_suffix != package.new_suffix)
            and package_source_files_url
        ):
            self.logger.info(f"[Info]: {package.new_version} is a minor release")

            # Some Arch packages do have versions that look like this: 1:1.16.5-2
            # On their repository host (Gitlab) the tags do like this: 1-1.16.5-2
            # In order to make a tag compare on Gitlab, use the altered versions
            package_changelog_temp = self.get_changelog_compare_package_tags(
                package_source_files_url,
                package.current_version_altered,
                package.new_version_altered,
                package_name_search,
                "minor",
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

        if package_changelog:
            return package_changelog
        else:
            return None

    def handle_intermediate_tags(
        self,
        intermediate_tags: List[Tuple[str, str]],
        package: List[namedtuple],
        package_name: str,
        package_source_files_url: str,
        package_upstream_url: str,
    ) -> Optional[List[Tuple[str, str, str, str, str]]]:
        """
        Process intermediate package tags and determine changelog entries between versions.

        This method compares each intermediate tag with its predecessor to identify
        whether it represents a minor or major release, then gathers changelog data
        accordingly. It uses Arch package and upstream sources to build a combined changelog.

        It also compares the final tag in the sequence against the current package version
        to ensure the last changelog diff is included.

        :param intermediate_tags: List of tuples containing intermediate version tags and their dates.
        :type intermediate_tags: List[Tuple[str, str]]
        :param package: A namedtuple-like structure containing version info about the package.
        :type package: List[namedtuple]
        :param package_name: The currently checked package name.
        :type package_name: str
        :param package_source_files_url: URL pointing to the Arch Linux package source files.
        :type package_source_files_url: str
        :param package_upstream_url: URL of the upstream source repository (e.g., GitHub, GitLab).
        :type package_upstream_url: str

        :return: A list of changelog entries found between intermediate tags, or None if none found.
        :rtype: Optional[List[Tuple[str, str, str, str, str]]]
        """
        package_changelog = []

        for index, (release, date) in enumerate(intermediate_tags):
            if index == 0:
                first_compare_main = package.current_main_altered
                first_compare_suffix = package.current_suffix
                first_compare_version = package.current_version_altered
            else:
                first_compare_version = intermediate_tags[index - 1][0]
                first_compare_main, first_compare_suffix = self.split_package_tag(first_compare_version)

            # Package tags can look like this:
            # 1-16.5-2 or 20240526-1
            if release.count("-") >= 2:
                second_compare_main = release.split("-")[0].replace("1:", "1-")
                second_compare_suffix = release.split("-")[2]
            else:
                second_compare_main = release.split("-")[0].replace("1:", "1-")
                second_compare_suffix = release.split("-")[1]

            # Check if there was a minor release in between
            # Example: 1.16.5-2 -> 1.16.5-3
            # Some Arch packages do have versions that look like this: 1:1.16.5-2
            # On their repository host (Gitlab) the tags do like this: 1-1.16.5-2
            # In order to make a tag compare on Gitlab, use the altered versions
            if first_compare_main == second_compare_main and first_compare_suffix != second_compare_suffix:
                self.logger.info(f"[Info]: {release} is a minor intermediate release")

                package_changelog_temp = self.get_changelog_compare_package_tags(
                    package_source_files_url,
                    first_compare_version,
                    release,
                    package_name,
                    "minor",
                    release,
                )

                if package_changelog_temp:
                    package_changelog += package_changelog_temp

            # Check if there was a major release in between
            # Example: 1.16.5-1 -> 1.16.6-1
            elif first_compare_main != second_compare_main:
                self.logger.info(f"[Info]: {release} is a major intermediate release")

                # Always get the Arch package changelog too, which is the same as the "minor" release case
                package_changelog_temp = self.get_changelog_compare_package_tags(
                    package_source_files_url,
                    first_compare_version,
                    release,
                    package_name,
                    "arch",
                )

                if package_changelog_temp:
                    package_changelog += package_changelog_temp

                package_changelog_temp = self.get_package_changelog_upstream_source(
                    package_upstream_url,
                    package_source_files_url,
                    package,
                    first_compare_version,
                    release,
                    package_name,
                    release,
                )

                if package_changelog_temp:
                    package_changelog += package_changelog_temp
            else:
                continue

        # Check if the last intermediate tag is a minor release
        if second_compare_main == package.new_main and second_compare_suffix != package.new_suffix:
            self.logger.info(f"[Info]: {package.new_version_altered} is a minor release (after intermediate release)")

            package_changelog_temp = self.get_changelog_compare_package_tags(
                package_source_files_url,
                release,
                package.new_version,
                package_name,
                "minor",
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

        # Check if the last intermediate tag is a major release
        elif second_compare_main != package.new_main:
            self.logger.info(f"[Info]: {package.new_version_altered} is a major release (after intermediate release)")

            # Always get the Arch package changelog too, which is the same as the "minor" release case
            package_changelog_temp = self.get_changelog_compare_package_tags(
                package_source_files_url,
                release,
                package.new_version,
                package_name,
                "arch",
                package.new_version_altered,
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

            package_changelog_temp = self.get_package_changelog_upstream_source(
                package_upstream_url,
                package_source_files_url,
                package,
                release,
                package.new_version,
                package_name,
                package.new_version_altered,
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

        if package_changelog:
            return package_changelog
        else:
            return None

    def get_package_architecture(self, package_name: str) -> str:
        """Retrieves the architecture of a specified package using `pacman`.
        This function runs `pacman -Q --info <package_name>` to obtain information about the
        package, then parses the output to extract the architecture of the package.

        :param package_name: The name of the upgradable package whose architecture should be retrieved.
        :type package_name: str
        :return: The architecture of the specified package.
        :rtype: str
        """
        try:
            result = subprocess.run(
                ["pacman", "-Q", "--info", package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        except subprocess.CalledProcessError as ex:
            self.logger.error(f"[Error]: Command '{ex.cmd}' returned non-zero exit status {ex.returncode}.")
            self.logger.error("[Error]: Standard Error:")
            self.logger.error(ex.stderr)
            exit(1)
        except PermissionError:
            self.logger.error(
                "[Error]: Permission denied. Are you sure you have the necessary permissions to run this command?"
            )
            exit(1)
        except Exception as ex:
            self.logger.error(f"[Error]: An unexpected error occurred: {ex}")
            exit(1)

        output = result.stdout.splitlines()
        package_architecture = None

        for line in output:
            if line.startswith(self.config.config.get("architecture-wording")):
                package_architecture = line.split(":")[1].strip()
                self.logger.debug(f"[Debug]: Package architecture: {package_architecture}")
                break

        if not package_architecture:
            self.logger.error(
                "[Error]: Couldn't find the package architecture in the output. "
                "If your system language is not set to English, update the 'architecture-wording' value "
                "in the config file to match the correct architecture label. "
                "You can find it by running 'sudo pacman -Q --info ANY-PACKAGE'. "
                "The location of the config file is shown when you start the program."
            )
            exit(1)

        return package_architecture

    def get_arch_package_compare_information(self, url: str) -> Optional[Dict[str, Optional[str]]]:
        """Extracts the source URL and associated tag information from an Arch package compare webpage.

        This function sends an HTTP GET request to the specified URL, parses the HTML content,
        and searches for lines that start with "source = https" or "source = git+https". It then
        extracts the source URLs for both the old and new package versions. Depending on the URL type,
        it extracts a base URL segment and, if available, a version tag (e.g., "#tag=...").

        The function computes a similarity ratio between the extracted base URLs using SequenceMatcher.
        If the similarity is >= 0.8, it returns a dictionary with the following keys:

        - "new_source_url": The extracted new source URL.
        - "old_source_url": The extracted old source URL.
        - "new_source_tag": The extracted tag from the new URL (if available).
        - "old_source_tag": The extracted tag from the old URL (if available).

        If the HTTP request fails, no valid source URLs are found, or the similarity ratio is below the
        threshold, the function returns None.

        :param url: The compare URL of the Arch package.
        :type url: str
        :return: Dict with keys: 'new_source_url', 'old_source_url', 'new_source_tag', 'old_source_tag',
             or None if extraction fails or similarity is too low.
        :rtype: Optional[Dict[str, Optional[str]]]
        """
        try:
            response = self.web_scraper.fetch_page_content_old(url)
            if not response:
                self.logger.debug(f"[Debug]: No response received from {url}")
                return None

            old_lines = self.web_scraper.find_all_elements(response, "tr", class_="line_holder old")

            new_lines = self.web_scraper.find_all_elements(response, "tr", class_="line_holder new")

            # Example on how the URL's could look like:
            # source = expat::git+https://github.com/libexpat/libexpat?signed#tag=R_2_7_0
            #
            source_urls_old = []
            source_urls_new = []

            for line in old_lines:
                text = line.get_text(strip=True)
                match = re.search(r"(https://).*", text)
                if match:
                    source_urls_old.append(match.group(0))

            for line in new_lines:
                text = line.get_text(strip=True)
                match = re.search(r"(https://).*", text)
                if match:
                    source_urls_new.append(match.group(0))

            if not source_urls_old or not source_urls_new:
                self.logger.debug(f"[Debug]: Couldn't find source nodes either for new or old in {url}")
                return None

            max_length = max(len(source_urls_old), len(source_urls_new))

            for i in range(max_length):
                old_url = source_urls_old[i] if i < len(source_urls_old) else None
                new_url = source_urls_new[i] if i < len(source_urls_new) else None

                # 'old_url' or `new_url` could extract something like this:
                # https://gitlab.freedesktop.org/pipewire/pipewire.git#tag=1.2.3
                # We only need this segment: https://gitlab.freedesktop.org/pipewire/
                if old_url and new_url:
                    self.logger.debug(f"[Debug]: Source URL raw old: {old_url}")
                    self.logger.debug(f"[Debug]: Source URL raw new: {new_url}")

                    # Handle URL's
                    #
                    if ".git" in old_url or ".git" in new_url:
                        # The URL could look like this:
                        # https://git.kernel.org/pub/scm/utils/kernel/kmod/kmod.git#tag=v34.1?signed
                        # We only want to extract: https://git.kernel.org/pub/scm/utils/kernel/kmod/kmod.git
                        match_url_old = re.search(r"https://.*?\.git", old_url)
                        match_url_new = re.search(r"https://.*?\.git", new_url)
                    elif "github" in old_url or "github" in new_url:
                        # The URL could look like this:
                        # https://github.com/libexpat/libexpat?signed#tag=R_2_7_0
                        # https://github.com/abseil/abseil-cpp/archive/20250127.0/abseil-cpp-20250127.0.tar.gz
                        # We only want to extract: https://github.com/abseil/abseil-cpp/
                        match_url_old = re.search(r"https://github\.com/[^/]+/[^/?]+", old_url)
                        match_url_new = re.search(r"https://github\.com/[^/]+/[^/?]+", new_url)
                    else:
                        match_url_old = re.search(r"https://.*?(?=#|$)", old_url)
                        match_url_new = re.search(r"https://.*?(?=#|$)", new_url)

                    # Handle tags
                    #
                    if ("gitlab" in old_url or "git." in old_url) or ("gitlab" in new_url or "git." in new_url):
                        # The URL could look like this:
                        # https://gitlab.freedesktop.org/pipewire/pipewire.git#tag=1.2.3
                        # https://git.kernel.org/pub/scm/utils/kernel/kmod/kmod.git#tag=v34.1?signed
                        # We only need this segment: "1.2.3"
                        match_tag_old = re.search(r"#tag=([^\?]+)", old_url)
                        match_tag_new = re.search(r"#tag=([^\?]+)", new_url)
                    elif "github" in old_url or "github" in new_url:
                        # The URL could look like this:
                        # https://github.com/docker/cli.git#tag=v28.0.1
                        # https://github.com/libexpat/libexpat?signed#tag=R_2_7_0
                        match_tag_old = re.search(r"#tag=([^\?]+)", old_url)
                        match_tag_new = re.search(r"#tag=([^\?]+)", new_url)

                        # or:
                        # https://github.com/libusb/libusb/releases/download/v1.0.28/...
                        # https://github.com/abseil/abseil-cpp/archive/20250127.0/...
                        if not match_tag_old:
                            match_tag_old = re.search(r"/(?:download|archive)/([^/]+)", old_url)

                        if not match_tag_new:
                            match_tag_new = re.search(r"/(?:download|archive)/([^/]+)", new_url)
                    else:
                        match_tag_old = None
                        match_tag_new = None

                    if match_url_old:
                        self.logger.debug(f"[Debug]: Source URL old: {match_url_old.group(0)}")
                    else:
                        self.logger.debug("[Debug]: Source URL old: None")
                    if match_url_new:
                        self.logger.debug(f"[Debug]: Source URL new: {match_url_new.group(0)}")
                    else:
                        self.logger.debug("[Debug]: Source URL new: None")
                    if match_tag_old:
                        self.logger.debug(f"[Debug]: Source tag old: {match_tag_old.group(1)}")
                    else:
                        self.logger.debug("[Debug]: Source tag old: None")
                    if match_tag_new:
                        self.logger.debug(f"[Debug]: Source tag new: {match_tag_new.group(1)}")
                    else:
                        self.logger.debug("[Debug]: Source tag new: None")

                    if match_url_old is not None and match_url_new is not None:
                        similarity = SequenceMatcher(None, match_url_old.group(0), match_url_new.group(0)).ratio()
                    else:
                        similarity = 0.0

                    # Both URL's are similar
                    if similarity >= 0.8:
                        return {
                            "new_source_url": (match_url_new.group(0) if match_url_new else None),
                            "old_source_url": (match_url_old.group(0) if match_url_old else None),
                            "new_source_tag": (match_tag_new.group(1) if match_tag_new else None),
                            "old_source_tag": (match_tag_old.group(1) if match_tag_old else None),
                        }
                    else:
                        return None
                else:
                    self.logger.debug(f"[Debug]: Couldn't extract either old_url or new_url")
                    return None
            else:
                self.logger.error(f"[Error]: Couldn't find 'source =' in {url}")
                return None

        except Exception as ex:
            self.logger.error(f"[Error]: Unexpected error while processing URL {url}: {ex}")
            return None

    def get_package_repository(
        self,
        enabled_repositories: List[str],
        package_name: str,
        package_architecture: str,
    ) -> str:
        """Determines the repository from which a specified package can be retrieved.
        This function checks the availability of the specified package in each of the enabled repositories.
        It constructs URLs for each repository based on the package name and architecture, and verifies
        their reachability. If multiple repositories are found to be reachable, an error is logged, and the
        program exits, as the user should configure either stable or testing repositories exclusively.

        :param enabled_repositories: A list of enabled repository names to check (from config file).
        :type enabled_repositories: List[str]
        :param package_name: The name of the package to check.
        :type package_name: str
        :param package_architecture: The architecture of the package (e.g., 'x86_64').
        :type package_architecture: str
        :return: The name of the reachable repository if exactly one is found.
        :rtype: str
        """
        reachable_repository = []
        for repository in enabled_repositories:
            possible_url = f"https://archlinux.org/packages/{repository}/{package_architecture}/{package_name}/"

            if self.web_scraper.check_website_availabilty(possible_url):
                reachable_repository.append(repository)

        # Multiple repositories from Arch do contain the same package.
        # The versions could be the same but could also differ.
        # This is an error of the user and he should either enable the stable
        # repositories or the testing in the config file.
        if len(reachable_repository) > 1:
            self.logger.error(
                "[Error]: Multiple repositories found. Please use either stable or testing in the config file."
            )
            exit(1)
        else:
            return reachable_repository

    def get_package_source_files_url(self, url: str) -> Optional[str]:
        """Retrieves the URL for the source files of a package from a webpage.
        This function sends an HTTP GET request to the specified URL, parses the HTML content to find a link with the
        text 'Source Files', and returns the URL of that link. If the 'Source Files' link is not found, the function
        returns `None`.

        04.06.2025:
        This function is currently not in use. It is still here as a backup if the current simple implementation
        which replaced this function is not enough

        :param url: The URL of the webpage to retrieve and parse.
        :type url: str
        :return: The URL of the 'Source Files' link if found, or `None` if the link is not found.
        :rtype: Optional[str]
        """
        try:
            response = self.web_scraper.fetch_page_content(url)
            if not response:
                self.logger.debug(f"[Debug]: No response received from {url}")
                return None

            source_file_link = self.web_scraper.find_element(response, "a", string="Source Files")

            if source_file_link:
                source_file_url = source_file_link.get("href")
                self.logger.info(f"[Info]: Arch 'Source Files' URL: {source_file_url}")
                return source_file_url
            else:
                self.logger.error(f"[Error]: Couldn't find node 'Source Files' on {url}")
                return None
        except Exception as ex:
            self.logger.error(f"[Error]: An unexpected error occurred while parsing the HTML: {ex}")
            return None

    def get_package_tags(
        self, url: str, base_url: Optional[str] = None, project_path: Optional[str] = None
    ) -> Optional[List[Tuple[str, str]]]:
        """Retrieves release tags and their associated timestamps from a source code hosting website.
        This function sends an HTTP GET request to the specified URL, parses the HTML content to find
        SVG elements representing tags and their corresponding timestamps. It then returns a list of tuples
        where each tuple contains a release tag and its associated timestamp. The function also transforms
        tags with a version prefix of '1:' to '1-' for compatibility with repository host formats.

        :param url: The URL of the webpage to retrieve and parse.
        :type url: str
        :param base_url: API endpoint, e.g. use GitLabAPI.base_urls for common types, e.g. https://gitlab.archlinux.org/api/v4
        :type base_url: str
        :param project_path: path to the package for the API, e.g. 'archlinux/packaging/packages/linux'
        :type project_path: str
        :return: A list of tuples where each tuple contains a release tag and its associated timestamp.
                 The timestamp has the format: 2024-12-30T19:45:26.000Z
                 If an error occurs during the request or parsing, or if no relevant data is found, None is returned.
        :rtype: Optional[List[Tuple[str, str]]]
        """
        try:
            if "gitlab" in url:
                if base_url and project_path:
                    combined_info = self.gitlab_api.get_package_tags(base_url, project_path)
                else:
                    self.logger.debug(
                        f"[Debug]: base_url or project_path is missing for {url} to fetch the release tags"
                    )
                    return None

                if not combined_info:
                    self.logger.debug(f"[Debug]: No release tags found in {url}")
                    return None
            elif "github" in url:
                response = self.web_scraper.fetch_page_content(url)
                if not response:
                    self.logger.debug(f"[Debug]: No response received from {url}")
                    return None

                # TODO: Currently it does not search for further tags if the Github page has a "Next" button.
                release_tags_raw = self.web_scraper.find_all_elements(response, "a", class_="Link--primary")

                if not release_tags_raw:
                    return None

                release_tags = [tag.text.strip() for tag in release_tags_raw]
                time_tags_raw = self.web_scraper.find_all_elements(response, "relative-time")

                if not time_tags_raw:
                    return None
            else:  # TODO: Check if this is needed outside of the old GitLab implementation
                response = self.web_scraper.fetch_page_content(url)
                if not response:
                    self.logger.debug(f"[Debug]: No response received from {url}")

                release_tags_raw = self.web_scraper.find_all_elements(
                    response, "svg", attrs={"data-testid": "tag-icon"}
                )

                if not release_tags_raw:
                    self.logger.debug(f"[Debug]: No raw release tags found in {url}")
                    return None

                release_tags = [tag.find_next("a").text for tag in release_tags_raw]
                time_tags_raw = self.web_scraper.find_all_elements(response, "time")

                if not time_tags_raw:
                    self.logger.debug(f"[Debug]: No raw time tags found in {url}")
                    return None

            if "gitlab" not in url:
                time_tags = [tag["datetime"] for tag in time_tags_raw]
                combined_info = list(zip(release_tags, time_tags))

            for index, (tag, creation_date) in enumerate(combined_info):
                # Some Arch packages do have versions that look like this: 1:1.16.5-2
                # On their repository host (GitLab) the tags do like this: 1-1.16.5-2
                # In order to make a tag compare on GitLab, transform '1:' to '1-'
                transformed_tag = tag.replace("1:", "1-")
                self.logger.debug(f"[Debug]: Release tag: {transformed_tag} Creation date: {creation_date}")
                combined_info[index] = (transformed_tag, creation_date)

            return combined_info
        except Exception as ex:
            self.logger.error(
                f"[Error]: An unexpected error occurred while parsing the HTML or extracting tag information: {ex}"
            )
            return None

    def get_package_changelog_upstream_source(
        self,
        package_upstream_url: str,
        package_source_files_url: str,
        package: List[namedtuple],
        current_tag: str,
        new_tag: str,
        package_name: str,
        override_shown_tag: Optional[str] = None,
    ) -> Optional[List[Tuple[str, str, str, str, str]]]:
        """Processes upstream package sources and retrieves changelog information
        by comparing different package versions from various upstream sources.

        Depending on the package upstream URL, the function determines how to retrieve
        and compare package versions. It supports GitHub, GitLab, KDE, and Arch Linux
        package sources. If a changelog is available, it is added to the package changelog list.

        :param package_upstream_url: The upstream source URL of the package.
        :type package_upstream_url: str
        :param package_source_files_url: The upstream URL of the package.
        :type package_source_files_url: str
        :param package: A named tuple containing the package information, such as the package name,
                        current version, new version, main version tags, and suffixes.
        :type package: namedtuple
        :param current_tag: The current version tag of the package.
        :type current_tag: str
        :param new_tag: The new version tag of the package.
        :type new_tag: str
        :param package_name: The name of the package.
        :type package_name: str
        :param override_shown_tag: Optional override for the displayed version tag.
        :type override_shown_tag: Optional[str], default is None
        :return: A list of tuples containing changelog information.
                 Each tuple consists of (source_url, old_version, new_version, package_name, release_type).
                 Returns None if no changelog information is found.
        :rtype: Optional[List[Tuple[str, str, str, str, str]]]
        """
        package_changelog = []
        match package_upstream_url:
            case url if "gitlab" in url:
                # Some package upstream URL's could look like this from the .nvchecker.toml file:
                # https://gitlab.archlinux.org/archlinux/packaging/packages/xorg-server/-/tags
                # We only need:
                # https://gitlab.archlinux.org/archlinux/packaging/packages/xorg-server
                # otherwise when setting together the compare url tags link for the changelog file
                # it can cause invalid URL's for the user.
                parsed_upstream_url = urlparse(url)
                parts = parsed_upstream_url.path.strip("/").split("/")
                base_parts = parts[: parts.index("-")] if "-" in parts else parts
                url = f"{parsed_upstream_url.scheme}://{parsed_upstream_url.netloc}/{'/'.join(base_parts)}"

                self.logger.debug(f"[Debug]: GitLab API: Upstream URL {url}")

                package_upstream_url_information = self.gitlab_api.extract_upstream_url_information(url)

                if package_upstream_url_information:
                    package_changelog_temp = self.get_changelog_compare_package_tags(
                        url,
                        current_tag,
                        new_tag,
                        package_upstream_url_information[3] if package_upstream_url_information[3] else package_name,
                        "major",
                        override_shown_tag,
                        package_upstream_url_information[0],
                        package_upstream_url_information[1],
                        package_upstream_url_information[2],
                    )
                else:
                    self.logger.error(
                        f"[Error]: GitLab API: No package upstream information found for {package_upstream_url}"
                    )
                    return None

                if package_changelog_temp:
                    package_changelog += package_changelog_temp

            case url if "github.com" in url:
                package_changelog_temp = self.get_changelog_compare_package_tags(
                    url,
                    current_tag,
                    new_tag,
                    package_name,
                    "major",
                    override_shown_tag,
                )

                if package_changelog_temp:
                    package_changelog += package_changelog_temp

            case url if "kde.org" in url:
                current_main, current_suffix = self.split_package_tag(current_tag)
                new_main, new_suffix = self.split_package_tag(new_tag)

                package_changelog_temp = self.get_changelog_kde_package(
                    url, current_main, new_main, package_name, override_shown_tag
                )

                if package_changelog_temp:
                    package_changelog += package_changelog_temp

            case _:
                # Example:
                # https://gitlab.archlinux.org/archlinux/packaging/packages/abseil-cpp/-/compare/20240722.1-1...20250127.0-1
                compare_arch_tags_url = f"{package_source_files_url}/compare/{current_tag}...{new_tag}"

                arch_package_information = self.get_arch_package_compare_information(compare_arch_tags_url)

                if arch_package_information is None:
                    return None

                new_source_url = arch_package_information["new_source_url"]
                old_source_url = arch_package_information["old_source_url"]
                new_source_tag = arch_package_information["new_source_tag"]
                old_source_tag = arch_package_information["old_source_tag"]

                if all(
                    x is not None
                    for x in [
                        new_source_url,
                        old_source_url,
                        new_source_tag,
                        old_source_tag,
                    ]
                ):
                    package_changelog_temp = self.get_changelog_compare_package_tags(
                        new_source_url,
                        old_source_tag,
                        new_source_tag,
                        package_name,
                        "major",
                        override_shown_tag,
                    )

                    if package_changelog_temp:
                        package_changelog += package_changelog_temp

        return package_changelog if package_changelog else None

    def get_closest_package_tag(self, current_tag: str, tags: List[str], threshold: int = 70) -> Optional[str]:
        """
        Finds the closest matching version string based on fuzzy string similarity using RapidFuzz.

        :param current_tag: The current package tag string to compare.
        :type current_tag: str
        :param tags: A list of package tags strings.
        :type tags: List[str]
        :param threshold: Minimum similarity score (0–100) to consider a match.
        :type threshold: int
        :return: The most similar package tag string or None if no match is good enough.
        :rtype: Optional[str]
        """
        # Preprocess current_tag: remove leading digits + dash (e.g., "1-") and trailing "-1"
        cleaned_tag = re.sub(r"^(\d+-)|(-\d+$)", "", current_tag)

        matches = process.extract(cleaned_tag, tags, score_cutoff=threshold)

        if not matches:
            return None

        return matches[0][0]

    def get_changelog_compare_package_tags(
        self,
        source: str,
        current_tag: str,
        new_tag: str,
        package_name: str,
        release_type: str,
        override_shown_new_tag: Optional[str] = None,
        package_repository: Optional[str] = None,
        tld: Optional[str] = None,
        project_path: Optional[str] = None,
    ) -> Optional[List[Tuple[str, str, str, str, str]]]:
        """Gets commits between two tags in a Git repository and retrieves commit messages and URLs.
        This function constructs a URL to compare the two specified tags in a Git repository, retrieves
        the comparison page, and parses it to extract commit messages and their corresponding URLs.
        The function returns a list of tuples where each tuple contains a commit message and its full URL.

        :param source: The base URL of the Git repository.
        :type source: str
        :param current_tag: The tag to compare from.
        :type current_tag: str
        :param new_tag: The tag to compare to.
        :type new_tag: str
        :param package_name: The currently checked package name.
        :type package_name: str
        :param release_type: minor, major or arch.
        :type release_type: str
        :param override_shown_new_tag: This is only for major releases since the Arch package tag
               and the origin package tag can differentiate (optional, defaults to None). It is also needed
               for intermediate releases when checking the Arch package.
        :type override_shown_new_tag: Optional[str]
        :param package_repository: The top-level namespace or organization of the project, typically found
                                directly before the domain's TLD. For example:
                                - "gnome" in "https://gitlab.gnome.org/GNOME/adwaita-icon-theme"
                                - "archlinux" in "https://gitlab.archlinux.org/archlinux/packaging/packages/mesa"
        :type package_repository: str
        :param tld: The domain's TLD. For example: org, com etc.
        :type tld: str
        :param project_path: The relative path to the repository within the platform, typically including
                     groups, subgroups, but without the repository name. For example:
                     - "GNOME"
                     - "archlinux/packaging/packages"
        :type project_path: str
        :return: A list of tuples where each tuple contains a commit message, its full URL and the version tag.
        :rtype: Optional[List[Tuple[str, str, str, str, str]]]
        """
        # This is not needed for git hosting sites that do have an public API endpoint.
        # But it is always needed for the final changelog entry to which the user can access
        # the compare tags website frontend instead of the API JSON output.
        compare_tags_url = None
        closest_match_current_tag = None
        closest_match_new_tag = None

        if "major" in release_type:
            if "github" in source:
                upstream_package_tags = self.get_package_tags(source.rstrip("/") + "/tags")
            elif "gitlab" in source:
                if project_path:
                    subdomain = f"{package_repository}." if package_repository else ""
                    base_url = f"https://gitlab.{subdomain}{tld}/api/v4/projects"
                    project_full_path = f"{project_path}/{package_name}"

                    upstream_package_tags = self.gitlab_api.get_package_tags(base_url, project_full_path)
                else:
                    upstream_package_tags = None
            else:
                upstream_package_tags = self.get_package_tags(source.rstrip("/") + "/-/tags")

            if upstream_package_tags:
                # Log upstream package tags for debug reasons
                for tag, creation_date in upstream_package_tags:
                    self.logger.debug(f"[Debug]: Upstream package tag: {tag} Creation date: {creation_date}")

                # Check if the current_tag and the new_tag/override_shown_new_tag are not in the upstream package tags
                # If not, find the closest one to use
                tag_versions = [tag[0] for tag in upstream_package_tags]

                if current_tag not in upstream_package_tags:
                    closest_match_current_tag = self.get_closest_package_tag(current_tag, tag_versions)

                    if closest_match_current_tag:
                        self.logger.debug(
                            f"[Debug]: Similar tag for {current_tag} found in the upstream package repository: {closest_match_current_tag}"
                        )
                    else:
                        self.logger.debug(
                            f"[Debug]: No similar tag for {current_tag} found in the upstream package repository"
                        )

                if new_tag or override_shown_new_tag not in upstream_package_tags:
                    new_tag_to_check = override_shown_new_tag or new_tag
                    closest_match_new_tag = self.get_closest_package_tag(new_tag_to_check, tag_versions)

                    if closest_match_new_tag:
                        self.logger.debug(
                            f"[Debug]: Similar tag for {new_tag_to_check} found in the upstream package repository: {closest_match_new_tag}"
                        )
                    else:
                        self.logger.debug(
                            f"[Debug]: No similar tag for {new_tag_to_check} found in the upstream package repository"
                        )

                # GitHub compare tags URL: https://github.com/user/repo/compare/v1.0.0...v2.0.0
                compare_tags_url = (
                    f"{source.rstrip('/')}/compare/"
                    f"{(closest_match_current_tag or [current_tag])[0]}..."
                    f"{(closest_match_new_tag or [new_tag])[0]}"
                    if "github" in source
                    else f"{source.rstrip('/')}/-/compare/"
                    f"{closest_match_current_tag or current_tag}..."
                    f"{closest_match_new_tag or new_tag}"
                )
            else:
                self.logger.debug(f"[Debug]: No upstream package tags found for {source}")

        if not compare_tags_url:
            if "github" in source:
                compare_tags_url = f"{source.rstrip('/')}/-/compare/{current_tag}...{new_tag}"
            elif "git.kernel.org" in source:
                # Example:
                # https://web.git.kernel.org/pub/scm/utils/kernel/kmod/kmod.git/log/?id=v34.1&id2=v34
                compare_tags_url = f"{source}/log/?id={new_tag}&id2={current_tag}"
            else:
                compare_tags_url = f"{source.rstrip('/')}/compare/{current_tag}...{new_tag}"

        self.logger.debug(f"[Debug]: Compare tags URL: {compare_tags_url}")

        if "gitlab" not in source:
            response = self.web_scraper.fetch_page_content(compare_tags_url)
            if response is None:
                self.logger.debug(f"[Debug]: No response received from {compare_tags_url}")
                return None

        # TODO: If the source hosting site is Github which can display commits only on multiple pages, how
        #       should we handle that?
        if "github" in source:
            kwargs = "mb-1"
            tag = "p"
        else:
            kwargs = "commit-row-message"
            tag = "a"

        commits = None
        if "git.kernel.org" in source:
            commits = self.web_scraper.find_elements_between_two_elements(response, "tr", new_tag, current_tag)
        elif "gitlab" in source:
            if release_type == "arch" or release_type == "minor":
                commits = self.gitlab_api.get_commits_between_tags(
                    self.gitlab_api.base_urls["Arch"],
                    "archlinux/packaging/packages/" + package_name,
                    current_tag,
                    override_shown_new_tag if override_shown_new_tag else new_tag,
                )
            else:
                if project_path:
                    subdomain = f"{package_repository}." if package_repository else ""
                    base_url = f"https://gitlab.{subdomain}{tld}/api/v4/projects"
                    project_full_path = f"{project_path}/{package_name}"

                    commits = self.gitlab_api.get_commits_between_tags(
                        base_url,
                        project_full_path,
                        closest_match_current_tag if closest_match_current_tag else current_tag,
                        closest_match_new_tag if closest_match_new_tag else new_tag,
                    )
        else:
            commits = self.web_scraper.find_all_elements(response, tag, class_=kwargs)

        if not commits:
            self.logger.debug(f"[Debug]: No commit messages found in the response from {compare_tags_url}")
            return None

        if "git.kernel.org" in source:
            commit_messages = [commit.find("a").get_text(strip=True) for commit in commits]
        elif "gitlab" in source:
            commit_messages = [commit[0] for commit in commits]
        else:
            commit_messages = [commit.get_text(strip=True) for commit in commits]

        if "github" in source or "git.kernel.org" in source:
            commit_urls = [urljoin(source, commit.find("a")["href"]) for commit in commits]
        elif "gitlab" in source:
            commit_urls = [commit[2] for commit in commits]
        else:
            commit_urls = [urljoin(source, commit.get("href")) for commit in commits]

        version_tags = [override_shown_new_tag if override_shown_new_tag else new_tag] * len(commit_messages)
        package_names = [package_name] * len(commit_messages)
        release_types = [release_type] * len(commit_messages)
        compare_tags_urls = [compare_tags_url] * len(commit_messages)

        combined_info = list(
            zip(
                commit_messages,
                commit_urls,
                version_tags,
                package_names,
                release_types,
                compare_tags_urls,
            )
        )

        if combined_info:
            return combined_info
        else:
            return None

    def get_changelog_kde_package(
        self,
        url: str,
        current_main: str,
        new_main: str,
        package_name: str,
        override_shown_tag: Optional[str] = None,
    ) -> List[Tuple[str, str, str, str, str]]:
        """ """
        kde_package_categories = [
            "plasma",
            "frameworks",
            "utilities",
            "libraries",
            "system",
            "graphics",
            "accessibility",
            "education",
            "games",
        ]

        # KDE tags look like this: v6.1.3 while Arch uses it like this 1:6.1.3-1
        current_version_altered = "v" + current_main.replace("1:", "")
        new_version_altered = "v" + new_main.replace("1:", "")

        # The upstream URL of KDE packages can look differently
        # - https://apps.kde.org/ark/
        # - https://community.kde.org/Frameworks
        # - https://kde.org/plasma-desktop/
        #
        # 1. Check if the upstream URL already contains the kde category
        #    - Example: https://archlinux.org/packages/extra/x86_64/ark/
        # 2. Try to open https://apps.kde.org/... and extract the category from there
        #    - Example: https://apps.kde.org/ark/
        # 3. Try to extract the category out of the `url = https://...` in .SRCINFO (To be implemented)
        #    - Example: https://gitlab.archlinux.org/archlinux/packaging/packages/ark/-/blob/main/.SRCINFO
        # 4. Brute force method, go through each KDE category and try if URL is reachable (To be implemented)
        #    - Example 1: https://invent.kde.org/frameworks/baloo-widgets
        #    - Example 2: https://invent.kde.org/libraries/baloo-widgets
        kde_category_found = False
        for tries in range(3):
            match tries:
                case 0:
                    kde_category = next(
                        (category for category in kde_package_categories if re.search(category, url, re.IGNORECASE)),
                        None,
                    )

                    if kde_category:
                        kde_category_found = True
                        self.logger.debug(f"[Debug]: KDE category: {kde_category}")
                        break
                case 1:
                    kde_category_url = "https://apps.kde.org/" + package_name

                    if not self.web_scraper.check_website_availabilty(kde_category_url):
                        self.logger.debug(f"[Debug]: Website: {kde_category_url} is not reachable")
                        break

                    response = self.web_scraper.fetch_page_content_old(kde_category_url)
                    if not response:
                        self.logger.debug(
                            f"[Debug]: No response received from {kde_category_url} while getting the KDE package changelog"
                        )
                        break

                    kde_category_raw = self.web_scraper.find_element(
                        response, "a", attrs={"href": re.compile(r"^/categories/.+")}
                    )

                    if kde_category_raw:
                        kde_category = kde_category_raw.text.strip()
                        kde_category_found = True
                        self.logger.debug(f"[Debug]: KDE category: {kde_category}")
                        break
                    else:
                        self.logger.error(f"[Error]: Couldn't extract KDE package category from {kde_category_url}")

        kde_gitlab_url = None
        if kde_category_found:
            for category in kde_package_categories:
                if category in kde_category.lower():
                    kde_gitlab_url = "https://invent.kde.org/" + category + "/" + package_name

            if not kde_gitlab_url:
                self.logger.error(f"[Error]: Unknown KDE GitLab group in: {kde_category}")
        else:
            for category in kde_package_categories:
                kde_gitlab_url = "https://invent.kde.org/" + category + "/" + package_name

                # We can't use the check_website_availability function of web_scraper since a wrong
                # URL won't lead to a 404 or another error return code but to a sign in page which
                # is interpreted as accessible.
                # Example:
                # - https://invent.kde.org/libraries/baloo-widgets (correct URL)
                # - https://invent.kde.org/plasma/baloo-widgets (wrong URL)
                # This is why we look for a specific element on the website which only exists on the
                # correct website.
                response = self.web_scraper.fetch_page_content_old(kde_gitlab_url)
                if not response:
                    self.logger.debug(
                        f"[Debug]: No response received from {kde_gitlab_url} while getting the KDE package changelog"
                    )
                    continue

                kde_package_name_extracted = self.web_scraper.find_element(
                    response, "a", text=lambda text: text and package_name in text
                )

                if kde_package_name_extracted is not None and package_name in kde_package_name_extracted.text:
                    self.logger.debug(f"[Debug]: KDE GitLab package URL: {kde_gitlab_url}")
                    break

        if kde_gitlab_url:
            package_changelog_temp = self.get_changelog_compare_package_tags(
                kde_gitlab_url,
                current_version_altered,
                new_version_altered,
                package_name,
                "major",
                override_shown_tag,
            )

            if package_changelog_temp:
                return package_changelog_temp
            else:
                return None
        else:
            return None

    def find_intermediate_tags(self, package_tags, current_tag: str, new_tag: str) -> Optional[List[Tuple[str, str]]]:
        """Finds and returns intermediate tags between the current and new version tags for a package.
        This method looks for tags between the current and new versions within a list of package tags.
        It ensures that intermediate versions are correctly identified, reversed if necessary, and returned
        for further processing.

        :param package_tags: A list of tuples containing release tags and their corresponding release times.
        :type package_tags: List[Tuple[str, str]]
        :param current_tag: The current version tag to start from.
        :type current_tag: str
        :param new_tag: The new version tag to search for.
        :type new_tag: str
        :return: A list of intermediate tags between the current and new versions, or None if no intermediate
                tags are found.
        :rtype: Optional[List[Tuple[str, str]]]
        """
        start_index = end_index = None

        current_tag_altered = current_tag.replace(":", "-")
        new_tag_altered = new_tag.replace(":", "-")

        for index, (release, time) in enumerate(package_tags):
            if release == current_tag_altered:
                end_index = index
            elif release == new_tag_altered:
                start_index = index

            if start_index is not None and end_index is not None:
                break

        if start_index is None or end_index is None:
            self.logger.error("[Error]: Intermediate tags. Either current_tag, new_tag or both were not found.")
            return None

        # Check if the intermediate tag(s) are really the next version of the current version
        # Example:
        # Client side:              1-1.12.2-1 (current version) -> 1-1.12.2-2 (new version)
        # Source code hosting side: 1-1.12.2-1 -> 1-13.2-1 -> 1-1.12.2-2
        intermediate_tags = package_tags[start_index + 1 : end_index]

        if intermediate_tags:
            # We need to reverse the found intermediate tags since source hosting sites always display
            # the tags from newest to oldest but we want to compare our current version with one version
            # newer and not directly with the newest.
            intermediate_tags.reverse()

            return intermediate_tags
        else:
            return None
