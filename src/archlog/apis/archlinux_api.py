import httpx
import urllib.parse
from typing import Optional, List, Dict, Tuple


class ArchLinuxAPI:
    """Handles anonymous access to the Arch Linux API for public data"""

    base_url = "https://archlinux.org/packages/search/json/?name="

    def __init__(self, logger) -> None:
        """Constructor method"""
        self.logger = logger

    def __get(self, package_name: str) -> Optional[List[Dict]]:
        """Sends a GET request to the ArchLinux API.

        :param package_name: The package name of the official Arch package
        :type package_name: str

        :return: Response object if successful, otherwise None
        :rtype: Optional[List[Dict]
        """
        url = f"{self.base_url}{package_name}"

        self.logger.debug(f"ArchLinux API URL: {url}")

        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as ex:
            self.logger.error(f"[Error]: ArchLinux API request failed: {ex}")
            return None

    def get_package_overview_site_information(self, package_name: str) -> Optional[Tuple[str, str, str]]:
        """
        Returns the upstream URL and the package description from the Arch package overview page.
        Example URL of Arch package overview page: https://archlinux.org/packages/extra/x86_64/bluez/

        :param package_name: The package name of the official Arch package
        :type package_name: str
        :return: [0] Upstream URL, [1] package base, [2] package description
        :rtype: Optional[Tuple[str, str, str]]
        """
        response = self.__get(package_name)
        if response:
            result = response.get("results", "")[0]
            return [result.get("url", ""), result.get("pkgbase"), result.get("pkgdesc", "")]
        else:
            return None

    def get_gitlab_package_url(self, package_name: str) -> str:
        """
        Returns the URL of the Arch package Git hosting site
        Example URL: https://gitlab.archlinux.org/archlinux/packaging/packages/ghidra

        :param package_name: The package name of the official Arch package
        :type package_name: str
        :return: URL of the Arch package Git hosting site
        :rtype: str
        """
        return f"https://gitlab.archlinux.org/archlinux/packaging/packages/{package_name}"
