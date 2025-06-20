import httpx
import urllib.parse
import re
import time
import base64
from typing import Optional, List, Dict, Tuple


class GitLabAPI:
    """Handles anonymous access to the GitLab API for public data.
    Documentation: https://docs.gitlab.com/api/rest/

    :param retries: Number of automatic retries for connection-related errors.
    :type retries: int
    :param timeout: Timeout in seconds for HTTP requests.
    :type timeout: float
    """

    # A list of known repositories which do have a lot of packages
    base_urls = {
        "Arch": "https://gitlab.archlinux.org/api/v4/projects",
        "Gnome": "https://gitlab.gnome.org/api/v4/projects",
    }

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

    def __get(
        self,
        base_url: str,
        endpoint: str,
        params: Optional[Dict] = None,
        max_attempts: int = 3,
        backoff_factor: int = 2,
    ) -> Optional[List[Dict]]:
        """Sends a GET request to the GitLab REST API with retry logic for certain HTTP status codes.

        If a retryable HTTP status code is returned (e.g., 429, 500, 503, see GitLabAPI.retry_status_codes), the method
        retries the request up to `max_attempts` times. Between attempts, it waits for
        an exponentially increasing delay calculated as:

            wait = backoff_factor ** (attempt_number - 1)

        For example, with a `backoff_factor` of 2, wait times between retries would be:
        1s (immediately after first failure), 2s, 4s, 8s, etc.

        :param base_url: Base URL of the API, e.g. https://gitlab.archlinux.org/api/v4
        :type base_url: str
        :param endpoint: API endpoint, e.g. 'projects/:id/repository/tags'
        :type endpoint: str
        :param params: Optional parameters at the end of the URL
        :type params: Optional[Dict]
        :param max_attempts: Total number of attempts before giving up (including the first try).
        :type max_attempts: int
        :param backoff_factor: Used for exponential backoff delay (in seconds).
        :type backoff_factor: int

        :return: Parsed JSON response if successful, otherwise None
        :rtype: Optional[List[Dict]
        """
        url = f"{base_url}/{endpoint.lstrip('/')}"
        self.logger.debug(f"GitLab API URL: {url}")

        for attempt in range(0, max_attempts):
            try:
                response = self.client.get(url, params=params)

                if response.status_code in self.retry_status_codes:
                    wait = backoff_factor**attempt
                    self.logger.debug(
                        f"GitLab API: [Retry {attempt}/{max_attempts}] HTTP {response.status_code} - retrying in {wait}s"
                    )
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as ex:  # this handles for example 404 or 403
                self.logger.error(f"[Error]: GitLab API request HTTP error: {ex}")

            except httpx.RequestError as ex:
                self.logger.error(f"[Error]: GitLab API request error: {ex}")

                if attempt == max_attempts:
                    return None
                time.sleep(backoff_factor**attempt)

        self.logger.error(f"[Error]: GitLab API: All retries failed.")
        return None

    def get_commits_between_tags(
        self, base_url: str, project_path: str, tag_from: str, tag_to: str
    ) -> Optional[List[Tuple[str, str, str]]]:
        """
        Returns a list of commits between two tags for a given GitLab project.
        Example URLs:
        - https://gitlab.archlinux.org/api/v4/projects/archlinux%2Fpackaging%2Fpackages%2Fmesa/repository/compare?from=1-25.0.4-1&to=1-25.0.5-1
        - https://gitlab.gnome.org/api/v4/projects/GNOME%2Fadwaita-icon-theme/repository/compare?from=48.0&to=48.1

        :param base_url: use GitLabAPI.base_urls for common types, e.g. https://gitlab.archlinux.org/api/v4
        :type base_url: str
        :param project_path: Project path, e.g. 'archlinux/packaging/packages/linux'
        :type project_path: str
        :param tag_from: Older tag (e.g. 'v6.8.arch1-1')
        :type tag_from: str
        :param tag_to: Newer tag (e.g. 'v6.8.arch1-2')
        :type tag_to: str
        :return: List of commit titles, their creation dates and the commit URL, or None on failure
        :rtype: Optional[List[Tuple[str, str, str]]]
        """
        encoded_path = urllib.parse.quote_plus(project_path)
        endpoint = f"{encoded_path}/repository/compare"
        params = {"from": tag_from, "to": tag_to}

        response = self.__get(base_url, endpoint, params=params)
        if response:
            return [
                (commit.get("title", ""), commit.get("created_at", ""), commit.get("web_url"))
                for commit in response.get("commits", "")
            ]
        else:
            return None

    def get_package_tags(self, base_url: str, project_path: str) -> Optional[List[Tuple[str, str]]]:
        """
        Returns a list of commits between two tags for a given GitLab project.
        Example URLs:
        - https://gitlab.archlinux.org/api/v4/projects/archlinux%2Fpackaging%2Fpackages%2Fmesa/repository/tags
        - https://gitlab.gnome.org/api/v4/projects/GNOME%2Fadwaita-icon-theme/repository/tags

        :param base_url: use GitLabAPI.base_urls for common types, e.g. https://gitlab.archlinux.org/api/v4
        :type base_url: str
        :param project_path: Project path, e.g. 'archlinux/packaging/packages/linux'
        :type project_path: str
        :return: List of package tags and their creation dates, or None on failure
        :rtype: Optional[List[Tuple[str, str]]]
        """
        encoded_path = urllib.parse.quote_plus(project_path)
        endpoint = f"{encoded_path}/repository/tags"

        response = self.__get(base_url, endpoint)
        if response:
            return [(tag.get("name", ""), tag.get("created_at", "")) for tag in response]
        else:
            return None

    def extract_upstream_url_information(self, upstream_url: str) -> Optional[Tuple[str, str, str]]:
        """
        Extracts the package repository and the project path of a given GitLab project URL and returns them.

        Example URL: https://gitlab.gnome.org/GNOME/adwaita-icon-theme
        package repository: gnome
        project path: GNOME
        package name: adwaita-icon-theme

        Example URL: https://gitlab.freedesktop.org/xorg/xserver/-/tags
        package repository: freedesktop
        project path: xorg
        package name: xserver

        :param upstream_url: The URL of the upstream GitLab repository
        :type upstream_url: str
        :return: A tuple containing the package repository (domain subpart), the project path (first path segment)
                and the project name, or None if the URL doesn't match the expected format.
        :rtype: Optional[Tuple[str, str, str]]
        """
        match = re.search(r"https://gitlab\.([^.]+)\.org/([^/]+)/([^/]+)", upstream_url)
        if match:
            package_repository = match.group(1)
            project_path = match.group(2)
            package_name = match.group(3)

            return package_repository, project_path, package_name
        return None

    def get_file_content(self, base_url: str, project_path: str, filename: str) -> Optional[str]:
        """
        Returns the "content" of a specific file decoded.
        Example URL:
        - https://gitlab.archlinux.org/api/v4/projects/archlinux%2Fpackaging%2Fpackages%2Fxorg-server/repository/files/.nvchecker.toml?ref=main

        :param base_url: use GitLabAPI.base_urls for common types, e.g. https://gitlab.archlinux.org/api/v4
        :type base_url: str
        :param project_path: Project path, e.g. 'archlinux/packaging/packages/linux'
        :type project_path: str
        :return: Content of page as str with utf-8 encoding, or None on failure
        :rtype: Optional[str]
        """
        encoded_path = urllib.parse.quote_plus(project_path)
        endpoint = f"{encoded_path}/repository/files/{filename}?ref=main"

        response = self.__get(base_url, endpoint)
        if response:
            return base64.b64decode(response.get("content")).decode("utf-8")
        else:
            return None
