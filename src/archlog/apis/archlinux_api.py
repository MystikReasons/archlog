import httpx
import urllib.parse
import time
from typing import Optional, List, Dict, Tuple


class ArchLinuxAPI:
    """Handles anonymous access to the Arch Linux API for public data

    :param retries: Number of automatic retries for connection-related errors.
    :type retries: int
    :param timeout: Timeout in seconds for HTTP requests.
    :type timeout: float
    """

    base_url = "https://archlinux.org/packages/search/json/?name="

    def __init__(self, logger, retries: int = 3, timeout: float = 10) -> None:
        """Constructor method"""
        self.logger = logger

        self.client = httpx.Client(timeout=timeout, transport=httpx.HTTPTransport(retries=retries))

        # Retry HTTP responses with these status codes:
        # 429: Too Many Requests - rate-limiting from the server
        # 500: Internal Server Error - generic unexpected server failure
        # 502: Bad Gateway - received an invalid response from upstream
        # 503: Service Unavailable - server is temporarily overloaded or under maintenance
        # 504: Gateway Timeout - server did not receive a timely response from upstream
        self.retry_status_codes = {429, 500, 502, 503, 504}

    def __get(self, package_name: str, max_attempts: int = 3, backoff_factor: int = 2) -> Optional[List[Dict]]:
        """Sends a GET request to the ArchLinux API.

        If a retryable HTTP status code is returned (e.g., 429, 500, 503, see ArchLinuxAPI.retry_status_codes), the method
        retries the request up to `max_attempts` times. Between attempts, it waits for
        an exponentially increasing delay calculated as:

            wait = backoff_factor ** (attempt_number - 1)

        For example, with a `backoff_factor` of 2, wait times between retries would be:
        1s (immediately after first failure), 2s, 4s, 8s, etc.

        :param package_name: The package name of the official Arch package
        :type package_name: str
        :param max_attempts: Total number of attempts before giving up (including the first try).
        :type max_attempts: int
        :param backoff_factor: Used for exponential backoff delay (in seconds).
        :type backoff_factor: int

        :return: Response object if successful, otherwise None
        :rtype: Optional[List[Dict]
        """
        url = f"{self.base_url}{package_name}"
        self.logger.debug(f"ArchLinux API URL: {url}")

        for attempt in range(max_attempts):
            try:
                response = self.client.get(url)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as ex:  # handles 4xx/5xx errors after raise_for_status()
                status_code = ex.response.status_code

                if status_code in self.retry_status_codes and attempt < max_attempts - 1:
                    wait = backoff_factor**attempt
                    self.logger.debug(
                        f"[Debug]: ArchLinux API: [Retry {attempt + 1}/{max_attempts}] HTTP {status_code} - retrying in {wait}s"
                    )
                    time.sleep(wait)
                    continue
                else:
                    self.logger.error(f"[Error]: ArchLinux API HTTP error {status_code}: {ex}")
                    return None

            except httpx.RequestError as ex:
                self.logger.error(f"[Error]: ArchLinux API request error: {ex}")

                if attempt < max_attempts - 1:
                    wait = backoff_factor**attempt
                    self.logger.debug(
                        f"[Debug]: ArchLinux API: [Retry {attempt + 1}/{max_attempts}] RequestError - retrying in {wait}s"
                    )
                    time.sleep(wait)
                    continue
                else:
                    return None

        self.logger.error(f"[Error]: ArchLinux API: All retries failed.")
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

        results = (response or {}).get("results") or []
        if results:
            result = results[0]
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
