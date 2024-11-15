from typing import Optional, List, Tuple, Dict, Any
from collections import namedtuple
from urllib.parse import urljoin, urlparse
from web_scraper import WebScraper
import re
import subprocess
import requests


class PackageHandler:
    def __init__(self, logger, config: Optional[Dict[str, Any]]) -> None:
        """
        Initializes an instance of the class with the necessary configuration and logger.
        Sets up the web scraper, logger, and loads the enabled repositories from the configuration.

        :param logger: Logger object for logging messages.
        :type logger: Logger
        :param config: Configuration object containing all required settings.
        :type config: Config
        :raises KeyError: If the configuration lacks 'arch-repositories'.
        :raises TypeError: If `logger` or `config` are not of the expected object types.
        """
        self.web_scraper = WebScraper()
        self.logger = logger
        self.config = config
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
        for repository in self.config.config.get("arch-repositories"):
            if repository.get("enabled"):
                self.enabled_repositories.append(repository.get("name"))

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
                text=True,  # This will prevent the output from doing this: "b'PACKAGE"
                check=True,  # This will raise an exception if the command fails
            )

            # Get the list of upgradable packages
            process = subprocess.run(
                ["sudo", "pacman", "-Qu"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,  # This will prevent the output from doing this: "b'PACKAGE"
                check=True,  # This will raise an exception if the command fails
            )

            packages_to_update = process.stdout.splitlines()
            packages_to_update = self.split_package_information(packages_to_update)
            return packages_to_update
        except subprocess.CalledProcessError as ex:
            self.logger.error(
                f"ERROR: Command '{ex.cmd}' returned non-zero exit status {ex.returncode}."
            )
            self.logger.error("Standard Error:")
            self.logger.error(ex.stderr)
            return None
        except PermissionError:
            self.logger.error(
                "ERROR: Permission denied. Are you sure you have the necessary permissions to run this command?"
            )
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
            parts = line.split(" ")
            package_name = parts[0]
            current_version = parts[1]
            # Some Arch packages do have versions that look like this: 1:1.16.5-2
            # On their repository host (Gitlab) the tags do like this: 1-1.16.5-2
            # To prevent repetitive code which replaces the symbol, we do it here
            current_version_altered = current_version.replace("1:", "1-")
            new_version = parts[3]
            new_version_altered = new_version.replace("1:", "1-")
            current_main = parts[1].split("-")[0]
            current_main_altered = current_main.replace("1:", "1-")
            new_main = parts[3].split("-")[0]
            current_suffix = parts[1].split("-")[1]
            new_suffix = parts[3].split("-")[1]

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

    def get_package_changelog(
        self, package: List[namedtuple]
    ) -> List[Tuple[str, str, str, str, str]]:
        """
        Generates a changelog for a specified package by analyzing intermediate, minor, and major releases
        between its current and new versions. It fetches and compares relevant metadata and tags from
        Arch Linux repositories, as well as upstream sources like GitHub, GitLab, and KDE GitLab.

        :param package: A named tuple containing the package information, such as the package name,
                        current version, new version, main version tags, and suffixes.
        :type package: List[namedtuple]
        :return: A list of tuples containing changelog information for the package. Each tuple provides
                details on each relevant change from intermediate, major, and minor versions, in the format:
                (tag, date, version, description, change type).
        :rtype: List[Tuple[str, str, str, str, str]]
        :raises ValueError: If the package's repository or architecture information cannot be found.
        :raises ConnectionError: If there are issues accessing external URLs for repository metadata.
        """
        package_changelog = []

        # To determine the exact arch package-adress we need the architecture and repository
        #                         repository  architecture
        #                                 |    |
        # https://archlinux.org/packages/core/any/automake/
        package_architecture = self.get_package_architecture(package.package_name)

        if not package_architecture:
            return None

        package_repository = self.get_package_repository(
            self.enabled_repositories, package.package_name, package_architecture
        )
        # TODO: package_repository should not be an array anymore in the future
        arch_package_url = (
            "https://archlinux.org/packages/"
            + package_repository[0]
            + "/"
            + package_architecture
            + "/"
            + package.package_name
        )
        package_upstream_url = self.get_package_upstream_url(arch_package_url)

        if not package_upstream_url:
            return None

        package_source_files_url = self.get_package_source_files_url(arch_package_url)

        if not package_source_files_url:
            return None

        ## TODO: Check if the source files (PKGBUILD, etc.) did receive some updates beside pkver, pkgrel, etc...
        # Always extract the package name from Arch's source control repository.
        # Example: https://gitlab.archlinux.org/archlinux/packaging/packages/nss -> nss
        arch_package_name = (
            urlparse(package_source_files_url).path.rstrip("/").split("/")[-1]
        )

        # Check if there were multiple releases on Arch side (either major or minor)
        # This will check the current local version with the first intermediate tag and then it will shift.
        # Example: current version -> 1st intermediate version (minor) -> 2nd intermediate version (major) -> ...
        # 1st iteration: current version -> 1st intermediate version (minor)
        # 2nd iteration: 1st intermediate version (minor) -> 2nd intermediate version (major)
        arch_package_tags = self.get_package_tags(package_source_files_url + "/-/tags")

        if not arch_package_tags:
            self.logger.error(
                f"ERROR: {arch_package_name}: Couldn't find any arch package tags"
            )
            return None

        intermediate_tags = self.find_intermediate_tags(
            arch_package_tags, package.current_version, package.new_version
        )
        if intermediate_tags:
            self.logger.info(f"Intermediate tags: {intermediate_tags}")
            package_changelog_temp = self.handle_intermediate_tags(
                intermediate_tags,
                package,
                package_source_files_url,
                package_upstream_url,
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

            if package_changelog:
                return package_changelog
            else:
                return None
        else:
            self.logger.info("No intermediate tags found")

        # Check if there was a major release
        # Example: 1.16.5-2 -> 1.17.5-1
        if package.current_main != package.new_main:
            self.logger.info(f"{package.new_version} is a major release")

            # Always get the Arch package changelog too, which is the same as the "minor" release case
            package_changelog_temp = self.get_changelog_compare_package_tags(
                package_source_files_url,
                package.current_version_altered,
                package.new_version_altered,
                package.package_name,
                "arch",
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

            match package_upstream_url:
                case url if "github.com" in url:
                    package_changelog_temp = self.get_changelog_compare_package_tags(
                        package_upstream_url,
                        package.current_version_altered,
                        package.new_version_altered,
                        arch_package_name,
                        "major",
                        package.new_version_altered,
                    )

                    if package_changelog_temp:
                        package_changelog += package_changelog_temp

                case url if "gitlab.com" in url:
                    package_changelog_temp = self.get_gitlab_changelog(
                        package_upstream_url, package.current_main, package.new_main
                    )

                    if package_changelog_temp:
                        package_changelog += package_changelog_temp

                case url if "kde.org" in url:
                    kde_package_categories = [
                        "plasma",
                        "framework",
                        "utilities",
                        "libraries",
                    ]

                    # KDE tags look like this: v6.1.3 while Arch uses it like this 1:6.1.3-1
                    current_version_altered = "v" + package.current_main.replace(
                        "1:", ""
                    )
                    new_version_altered = "v" + package.new_main.replace("1:", "")

                    # The upstream link of KDE packages can look differently
                    # - https://apps.kde.org/ark/
                    # - https://community.kde.org/Frameworks
                    # - https://kde.org/plasma-desktop/
                    #
                    # 1. Check if the upstream URL already contains the kde category
                    #    - Example: https://archlinux.org/packages/extra/x86_64/ark/
                    # 2. Try to open https://apps.kde.org/... and extract the category from there
                    #    - Example: https://apps.kde.org/ark/
                    # 3. Try to extract the category out of the `source = https://...` in .SRCINFO (To be implemented)
                    #    - Example: https://gitlab.archlinux.org/archlinux/packaging/packages/ark/-/blob/main/.SRCINFO
                    # 4. Brute force method, go through each KDE category and try if URL is reachable (To be implemented)
                    #    - Example 1: https://invent.kde.org/frameworks/baloo-widgets
                    #    - Example 2: https://invent.kde.org/libraries/baloo-widgets
                    kde_category = next(
                        (
                            category
                            for category in kde_package_categories
                            if re.search(category, url, re.IGNORECASE)
                        ),
                        None,
                    )

                    if kde_category:
                        self.logger.debug(f"KDE category: {kde_category}")
                    else:
                        kde_category_url = (
                            "https://apps.kde.org/" + package.package_name
                        )

                        response = self.web_scraper.fetch_page_content(kde_category_url)
                        kde_category_raw = self.web_scraper.find_element(
                            response,
                            "a",
                            attrs={"href": re.compile(r"^/categories/.+")},
                        )

                        if kde_category_raw:
                            kde_category = kde_category_raw.text.strip()
                            self.logger.debug(f"KDE category: {kde_category}")
                        else:
                            self.logger.error(
                                f"ERROR: Couldn't extract KDE package category from {kde_category_url}"
                            )
                            return package_changelog if package_changelog else None

                    # Differentiate between different KDE package groups (Gitlab)
                    if "plasma" in kde_category.lower():
                        base_url = "https://invent.kde.org/plasma/"
                    elif "framework" in kde_category.lower():
                        base_url = "https://invent.kde.org/frameworks/"
                    elif "utilities" in kde_category.lower():
                        base_url = "https://invent.kde.org/utilities/"
                    elif "libraries" in kde_category.lower():
                        base_url = "https://invent.kde.org/libraries"
                    else:
                        self.logger.error(
                            f"ERROR: Unknown KDE Gitlab group in: {kde_category}"
                        )
                        return package_changelog if package_changelog else None

                    package_changelog_temp = self.get_changelog_compare_package_tags(
                        base_url + package.package_name,
                        current_version_altered,
                        new_version_altered,
                        arch_package_name,
                        "major",
                        package.new_version_altered,
                    )

                    if package_changelog_temp:
                        package_changelog += package_changelog_temp

                case _:
                    current_tag_url = (
                        package_source_files_url
                        + "/-/blob/"
                        + package.current_version_altered
                        + "/.SRCINFO"
                    )
                    new_tag_url = (
                        package_source_files_url
                        + "/-/blob/"
                        + package.new_version_altered
                        + "/.SRCINFO"
                    )
                    self.logger.debug(f"Current tag URL: {current_tag_url}")
                    self.logger.debug(f"New tag URL: {new_tag_url}")
                    # https://gitlab.archlinux.org/archlinux/packaging/packages/pipewire/-/blob/1-1.2.3-1/.SRCINFO

                    first_source_url = self.get_arch_package_source_url(current_tag_url)
                    second_source_url = self.get_arch_package_source_url(new_tag_url)
                    first_source_tag = self.get_arch_package_source_tag(current_tag_url)
                    second_source_tag = self.get_arch_package_source_tag(new_tag_url)

                    if first_source_url != second_source_url:
                        return package_changelog if package_changelog else None

                    if (
                        not first_source_url
                        or not second_source_url
                        and not first_source_tag
                        or not second_source_tag
                    ):
                        return package_changelog if package_changelog else None
                    else:
                        package_changelog_temp = (
                            self.get_changelog_compare_package_tags(
                                first_source_url,
                                first_source_tag,
                                second_source_tag,
                                arch_package_name,
                                "major",
                                package.new_version_altered,
                            )
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
            self.logger.info(f"{package.new_version} is a minor release")

            # Some Arch packages do have versions that look like this: 1:1.16.5-2
            # On their repository host (Gitlab) the tags do like this: 1-1.16.5-2
            # In order to make a tag compare on Gitlab, use the altered versions
            package_changelog_temp = self.get_changelog_compare_package_tags(
                package_source_files_url,
                package.current_version_altered,
                package.new_version_altered,
                package.package_name,
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
        intermediate_tags,
        package: List[namedtuple],
        package_source_files_url,
        package_upstream_url,
    ):
        package_changelog = []

        for index, (release, date) in enumerate(intermediate_tags):
            if index == 0:
                first_compare_main = package.current_main_altered
                first_compare_suffix = package.current_suffix
                first_compare_version = package.current_version_altered
            else:
                # Some package tags can look like this:
                # 1-16.5-2 or 20240526-1
                if intermediate_tags[index - 1][0].count("-") >= 2:
                    first_compare_main = (
                        intermediate_tags[index - 1][0]
                        .split("-")[:2]
                        .replace("1:", "1-")
                    )
                    first_compare_suffix = intermediate_tags[index - 1][0].split("-")[2]
                else:
                    first_compare_main = (
                        intermediate_tags[index - 1][0]
                        .split("-")[0]
                        .replace("1:", "1-")
                    )
                    first_compare_suffix = intermediate_tags[index - 1][0].split("-")[1]

                first_compare_version = intermediate_tags[index - 1][0]

            # Some package tags can look like this:
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
            if (
                first_compare_main == second_compare_main
                and first_compare_suffix != second_compare_suffix
            ):
                self.logger.info(f"{release} is a minor intermediate release")

                package_changelog_temp = self.get_changelog_compare_package_tags(
                    package_source_files_url,
                    first_compare_version,
                    release,
                    package.package_name,
                    "minor",
                    release,
                )

                if package_changelog_temp:
                    package_changelog += package_changelog_temp

            # Check if there was a major release in between
            elif first_compare_main != second_compare_main:
                self.logger.info(f"{release} is a major intermediate release")

                # Check if the 'source' does contain something like gitlab or github
                # when the 'Upstream URL' does not contain another source code hosting website
                first_tag_url = (
                    package_source_files_url
                    + "/-/blob/"
                    + first_compare_version
                    + "/.SRCINFO"
                )

                second_tag_url = (
                    package_source_files_url + "/-/blob/" + release + "/.SRCINFO"
                )
                self.logger.debug(f"First tag URL: {first_tag_url}")
                self.logger.debug(f"Second tag URL: {second_tag_url}")
                # https://gitlab.archlinux.org/archlinux/packaging/packages/pipewire/-/blob/1-1.2.3-1/.SRCINFO

                # Always get the Arch package changelog too, which is the same as the "minor" release case
                package_changelog_temp = self.get_changelog_compare_package_tags(
                    package_source_files_url,
                    first_compare_version,
                    release,
                    package.package_name,
                    "arch",
                    package.new_version_altered,
                )

                if package_changelog_temp:
                    package_changelog += package_changelog_temp

                first_source_url = self.get_arch_package_source_url(first_tag_url)
                second_source_url = self.get_arch_package_source_url(second_tag_url)
                first_source_tag = self.get_arch_package_source_tag(first_tag_url)
                second_source_tag = self.get_arch_package_source_tag(second_tag_url)

                if first_source_url != second_source_url:
                    continue

                if (
                    not first_source_url
                    or not second_source_url
                    and not first_source_tag
                    or not second_source_tag
                ):
                    continue
                else:
                    package_changelog_temp = self.get_changelog_compare_package_tags(
                        package_upstream_url,
                        first_source_tag,
                        second_source_tag,
                        package.package_name,
                        "major",
                        package.new_version_altered,
                    )

                    if package_changelog_temp:
                        package_changelog += package_changelog_temp

        # Check if the last intermediate tag is a minor release
        if (
            second_compare_main == package.new_main
            and second_compare_suffix != package.new_suffix
        ):
            self.logger.info(
                f"{package.new_version_altered} is a minor release (afer intermediate release)"
            )

            package_changelog_temp = self.get_changelog_compare_package_tags(
                package_source_files_url,
                release,
                package.new_version,
                package.package_name,
                "minor",
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp
        # Check if the last intermediate tag is a major release
        elif second_compare_main != package.new_main:
            self.logger.info(
                f"{package.new_version_altered} is a major release (afer intermediate release)"
            )

            # Always get the Arch package changelog too, which is the same as the "minor" release case
            package_changelog_temp = self.get_changelog_compare_package_tags(
                package_source_files_url,
                release,
                package.new_version,
                package.package_name,
                "arch",
                package.new_version_altered,
            )

            if package_changelog_temp:
                package_changelog += package_changelog_temp

            second_tag_url = (
                package_source_files_url + "/-/blob/" + release + "/.SRCINFO"
            )
            second_source_url = self.get_arch_package_source_url(second_tag_url)
            second_source_tag = self.get_arch_package_source_tag(second_tag_url)

            last_tag_url = (
                package_source_files_url
                + "/-/blob/"
                + package.new_version
                + "/.SRCINFO"
            )
            last_source_url = self.get_arch_package_source_url(last_tag_url)
            last_source_tag = self.get_arch_package_source_tag(last_tag_url)

            if (
                not second_source_url
                or not second_source_tag
                and not last_source_url
                or not last_source_tag
            ):
                if package_changelog:
                    return package_changelog
                else:
                    return None
            else:
                if second_source_url != last_source_url:
                    if package_changelog:
                        return package_changelog
                    else:
                        return None

                package_changelog_temp = self.get_changelog_compare_package_tags(
                    second_source_url,
                    second_source_tag,
                    last_source_tag,
                    package.package_name,
                    "major",
                    package.new_version_altered,
                )

                if package_changelog_temp:
                    package_changelog += package_changelog_temp

        if package_changelog:
            return package_changelog
        else:
            return None

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
                ["pacman", "-Q", "--info", package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        except subprocess.CalledProcessError as ex:
            self.logger.error(
                f"ERROR: Command '{ex.cmd}' returned non-zero exit status {ex.returncode}."
            )
            self.logger.error("Standard Error:")
            self.logger.error(e.stderr)
            exit(1)
        except PermissionError:
            self.logger.error(
                "ERROR: Permission denied. Are you sure you have the necessary permissions to run this command?"
            )
            exit(1)
        except Exception as ex:
            self.logger.error(f"ERROR: An unexpected error occurred: {ex}")
            exit(1)

        output = result.stdout.splitlines()

        for line in output:
            if line.startswith("Architecture"):  # TODO: Currently language-dependent
                package_architecture = line.split(":")[1].strip()
                self.logger.debug(f"Package architecture: {package_architecture}")
                break

        if not package_architecture:
            self.logger.error(
                "ERROR: Could not find package architecture in the output. Is the system language something else than English?"
            )
            return None

        return package_architecture

    def get_arch_package_source_url(self, url):
        """
        Extracts the source URL from an Arch source webpage (gitlab.archlinux.org) containing package information.

        This function sends an HTTP GET request to the specified URL, parses the HTML content
        to find a `<span>` tag containing the source URL of a package. It then extracts and
        returns the source URL. The function specifically looks for the string 'source =' in
        the `<span>` tag text and extracts the URL part before the final segment.

        :param str url: The URL of the webpage to retrieve and parse.
        :return: The extracted source URL if found, otherwise None.
        :rtype: str
        :raises requests.RequestException: If an error occurs during the HTTP request.
            This includes network errors, invalid URLs, or issues with the request itself.
        :raises Exception: For any other unexpected errors that occur during HTML parsing or URL extraction.
        """
        try:
            response = self.web_scraper.fetch_page_content(url)
            source_urls = self.web_scraper.find_all_elements(
                response, None, string=lambda text: "source =" in text
            )

            if not source_urls:
                self.logger.debug(f"Couldn't find a source node in {url}")
                return None

            for source_url in source_urls:
                source_url = source_url.get_text(strip=True)
                self.logger.debug(f"Source URL raw: {source_url}")

                # 'source_url' could extract something like this:
                # git+https://gitlab.freedesktop.org/pipewire/pipewire.git#tag=1.2.3
                # We only need this segment: https://gitlab.freedesktop.org/pipewire/
                if ".git" in source_url:
                    match = re.search(r"https://.*(?=\.git)", source_url)
                else:
                    match = re.search(r"https://.*(?=#)", source_url)

                if match:
                    source_url = match.group(0)
                    self.logger.debug(f"Source URL: {source_url}")
                    return source_url
                else:
                    self.logger.error(f"ERROR: Couldn't find 'source =' in {url}")
                    return None

        except requests.RequestException as ex:
            self.logger.error(f"ERROR: HTTP Request failed for URL {url}: {ex}")
            return None
        except Exception as ex:
            self.logger.error(
                f"ERROR: Unexpected error while processing URL {url}: {ex}"
            )
            return None

    def get_arch_package_source_tag(self, url):
        """
        Extracts the source tag from an Arch source webpage (gitlab.archlinux.org) containing package information.

        This function sends an HTTP GET request to the specified URL, parses the HTML content
        to find a `<span>` tag containing the source URL of a package. It then extracts and
        returns the source URL. The function specifically looks for the string 'source =' in
        the `<span>` tag text and extracts the URL part before the final segment.

        :param str url: The URL of the webpage to retrieve and parse.
        :return: The extracted source URL if found, otherwise None.
        :rtype: str
        :raises requests.RequestException: If an error occurs during the HTTP request.
            This includes network errors, invalid URLs, or issues with the request itself.
        :raises Exception: For any other unexpected errors that occur during HTML parsing or URL extraction.
        """
        try:
            response = self.web_scraper.fetch_page_content(url)
            source_urls = self.web_scraper.find_all_elements(
                response, None, string=lambda text: "source =" in text
            )

            if not source_urls:
                self.logger.debug(f"Couldn't find a source node in {url}")
                return None

            for source_url in source_urls:
                source_url = source_url.get_text(strip=True)

                # 'source_url' could extract something like this:
                # git+https://gitlab.freedesktop.org/pipewire/pipewire.git#tag=1.2.3
                # We only need this segment: https://gitlab.freedesktop.org/pipewire/
                match = re.search(r"#tag=([^\?]+)", source_url)

                if match:
                    source_tag = match.group(1)
                    self.logger.info(f"Source tag: {source_tag}")
                    return source_tag
                else:
                    self.logger.error(
                        f"ERROR: Couldn't find information 'tag=' in node 'source =' in {url}"
                    )
                    return None

        except requests.RequestException as ex:
            self.logger.error(f"ERROR: HTTP Request failed for URL {url}: {ex}")
            return None
        except Exception as ex:
            self.logger.error(
                f"ERROR: Unexpected error while processing URL {url}: {ex}"
            )
            return None

    def get_package_repository(
        self,
        enabled_repositories: List[str],
        package_name: str,
        package_architecture: str,
    ) -> str:
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
            possible_url = (
                "https://archlinux.org/packages/"
                + repository
                + "/"
                + package_architecture
                + "/"
                + package_name
            )

            if self.check_website_availabilty(possible_url):
                reachable_repository.append(repository)

        # Multiple repositories from Arch do contain the same package.
        # The versions could be the same but could also differ.
        # This is an error of the user and he should either enable the stable
        # repositories or the testing in the config file.
        if len(reachable_repository) > 1:
            self.logger.error(
                "ERROR: Multiple repositories found. Please use either stable or testing in the config file."
            )
            exit(1)
        else:
            return reachable_repository

    def get_package_upstream_url(self, url: str) -> Optional[str]:
        """
        Retrieves the upstream URL for a package from a specified Arch Linux package page.

        :param url: The URL of the Arch Linux package page to scrape for the upstream URL.
        :type url: str
        :return: The upstream URL as a string if found, or None if the URL is not available or
                if the node 'Upstream URL:' cannot be located.
        :rtype: Optional[str]
        :raises ConnectionError: If there is an issue fetching the page content.
        :raises AttributeError: If there is an unexpected structure on the page that prevents
                                accessing the upstream URL node.
        """
        response = self.web_scraper.fetch_page_content(url)
        if response is None:
            return None

        upstream_link = self.web_scraper.find_element(
            response, "th", string="Upstream URL:"
        )
        if upstream_link:
            upstream_url = upstream_link.find_next_sibling("td").find("a").get("href")
            self.logger.debug(f"Package upstream URL: {upstream_url}")
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

            source_file_link = self.web_scraper.find_element(
                response, "a", string="Source Files"
            )

            if source_file_link:
                source_file_url = source_file_link.get("href")
                self.logger.info(f"Arch 'Source Files' URL: {source_file_url}")
                return source_file_url
            else:
                self.logger.error(f"ERROR: Couldn't find node 'Source Files' on {url}")
                return None
        except requests.RequestException as ex:
            self.logger.error(
                f"ERROR: An error occurred during the HTTP request to {url}. Error code: {ex}"
            )
            return None
        except Exception as ex:
            self.logger.error(
                f"ERROR: An unexpected error occurred while parsing the HTML: {ex}"
            )
            return None

    def get_package_tags(self, url: str) -> List[Tuple[str, str]]:
        """
        Retrieves release tags and their associated timestamps from a source code hosting website.

        This function sends an HTTP GET request to the specified URL, parses the HTML content to find
        SVG elements representing tags and their corresponding timestamps. It then returns a list of tuples
        where each tuple contains a release tag and its associated timestamp. The function also transforms
        tags with a version prefix of '1:' to '1-' for compatibility with repository host formats.

        :param str url: The URL of the webpage to retrieve and parse.
        :return: A list of tuples where each tuple contains a release tag and its associated timestamp.
                 If an error occurs during the request or parsing, or if no relevant data is found, an empty list is returned.
        :rtype: List[Tuple[str, str]]
        :raises requests.RequestException: If an error occurs during the HTTP request.
            This includes network errors, invalid URLs, or issues with the request itself.
        :raises Exception: For any other unexpected errors that occur during HTML parsing.
        """
        try:
            response = self.web_scraper.fetch_page_content(url)

            if not response:
                return None

            svg = self.web_scraper.find_all_elements(
                response, "svg", attrs={"data-testid": "tag-icon"}
            )

            if not svg:
                self.logger.debug(f"No package tag found in the response from {url}")
                return None

            release_tags = [svg_tag.find_next("a").text for svg_tag in svg]
            time_tag = self.web_scraper.find_all_elements(response, "time")
            time_tags = [tag["datetime"] for tag in time_tag]

            combined_info = list(zip(release_tags, time_tags))

            for index, (release, time) in enumerate(combined_info):
                # Some Arch packages do have versions that look like this: 1:1.16.5-2
                # On their repository host (Gitlab) the tags do like this: 1-1.16.5-2
                # In order to make a tag compare on Gitlab, transform '1:' to '1-'
                transformed_release = release.replace("1:", "1-")
                self.logger.debug(
                    f"Release tag: {transformed_release} Time tag: {time}"
                )
                combined_info[index] = (transformed_release, time)

            return combined_info

        except requests.RequestException as ex:
            self.logger.error(
                f"ERROR: An error occurred during the HTTP request to {url}. Error code: {ex}"
            )
            return None
        except Exception as ex:
            self.logger.error(
                f"ERROR: An unexpected error occurred while parsing the HTML or extracting tag information: {ex}"
            )
            return None

    def get_changelog_compare_package_tags(
        self,
        source: str,
        current_tag: str,
        new_tag: str,
        package_name: str,
        release_type: str,
        arch_new_tag: Optional[str] = None,
    ) -> List[Tuple[str, str, str, str, str]]:
        """
        Gets commits between two tags in a Git repository and retrieves commit messages and URLs.

        This function constructs a URL to compare the two specified tags in a Git repository, retrieves
        the comparison page, and parses it to extract commit messages and their corresponding URLs.
        The function returns a list of tuples where each tuple contains a commit message and its full URL.

        :param str source: The base URL of the Git repository.
        :param str current_tag: The tag to compare from.
        :param str new_tag: The tag to compare to.
        :param str package_name: The currently checked package name.
        :param str release_type: minor, major or arch.
        :param Optional[str] arch_new_tag: This is only needed for major releases since the Arch package tag
               and the origin package tag can differentiate (optional, defaults to None).
        :return: A list of tuples where each tuple contains a commit message, its full URL and the version tag.
        :rtype: List[Tuple[str, str, str, str, str]]
        :raises requests.RequestException: If an error occurs during the HTTP request.
            This includes network errors, invalid URLs, or issues with the request itself.
        :raises Exception: For any other unexpected errors that occur during HTML parsing.
        """
        compare_tags_url = source + "/-/compare/" + current_tag + "..." + new_tag
        self.logger.debug(f"Compare tags URL: {compare_tags_url}")

        response = self.web_scraper.fetch_page_content(compare_tags_url)
        commits = self.web_scraper.find_all_elements(
            response, "a", class_="commit-row-message"
        )
        if not commits:
            self.logger.debug(
                f"No commit messages found in the response from {compare_tags_url}"
            )
            return None

        commit_messages = [commit.get_text(strip=True) for commit in commits]
        commit_urls = [urljoin(source, commit.get("href")) for commit in commits]
        version_tags = [arch_new_tag if arch_new_tag else new_tag] * len(
            commit_messages
        )
        package_names = [package_name] * len(commit_messages)
        release_types = [release_type] * len(commit_messages)

        combined_info = list(
            zip(
                commit_messages, commit_urls, version_tags, package_names, release_types
            )
        )

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
                self.logger.info(
                    f"Website: {url} returned status code {response.status_code}."
                )
                return False
        except requests.RequestException as ex:
            self.logger.error(
                f"ERROR: An error occured during checking availability of website {url}. Error code: {ex}"
            )
            return False

    def find_intermediate_tags(self, package_tags, current_tag: str, new_tag: str):
        """
        Finds and returns intermediate tags between the current and new version tags for a package.

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
        :raises ValueError: If neither the current_tag nor the new_tag is found in the package_tags.
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
            self.logger.error(
                "ERROR: Intermediate tags. Either current_tag, new_tag or both were not found."
            )
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

    def get_gitlab_changelog(
        self, url: str, current_tag: str, new_tag: str
    ) -> List[Tuple[str, str]]:
        self.logger.info("Checking Gitlab changelog")

        # TODO: This function still lacks functionality
        # Check if Arch versions are the same as the tags on Gitlab
        package_tags = self.get_package_tags(url + "/-/tags")
        if package_tags:
            self.logger.info("TODO")
        else:
            self.logger.info(f"No package tags on: {url + '/-/tags'} found")

        return None
