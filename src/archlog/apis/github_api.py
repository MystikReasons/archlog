import httpx
import re
import time
from typing import Optional, Dict, List, Tuple


class GitHubAPI:
    """Handles anonymous access to the GitHub API for public data.
    Documentation: https://docs.github.com/en/rest

    :param retries: Number of automatic retries for connection-related errors.
    :type retries: int
    :param timeout: Timeout in seconds for HTTP requests.
    :type timeout: float
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, logger, retries: int = 3, timeout: float = 10) -> None:
        """Constructor method"""
        self.logger = logger

        self.client = httpx.Client(timeout=timeout, transport=httpx.HTTPTransport(retries=retries))

        # Retry HTTP responses with these status codes:
        # 403: Forbidden – typically indicates GitHub primary rate limit exceeded (x-ratelimit-remaining=0),
        #      only retried if rate-limit headers are present
        # 429: Too Many Requests - rate-limiting from the server
        # 500: Internal Server Error - generic unexpected server failure
        # 502: Bad Gateway - received an invalid response from upstream
        # 503: Service Unavailable - server is temporarily overloaded or under maintenance
        # 504: Gateway Timeout - server did not receive a timely response from upstream
        self.retry_status_codes = {403, 429, 500, 502, 503, 504}

    def __get(
        self, endpoint: str, max_attempts: int = 3, backoff_factor: int = 2, page_size: int = 30
    ) -> Optional[List[Dict]]:
        """Sends a GET request to the GitHub REST API with retry logic for certain HTTP status codes.

        If a retryable HTTP status code is returned (e.g., 429, 500, 502, 503, 504, see GitHubAPI.retry_status_codes),
        the method retries the request up to `max_attempts` times. The delay between attempts is determined as follows:

            1. If the `retry-after` header is present, wait for the specified number of seconds.
            2. If `x-ratelimit-remaining` is 0 and `x-ratelimit-reset` is present, wait until the reset time (UTC epoch seconds).
            3. Otherwise, fall back to exponential backoff:

                wait = backoff_factor ** attempt_number

        For example, with a `backoff_factor` of 2, wait times would be:
        1s (first retry), 2s, 4s, 8s, etc.

        :param endpoint: API endpoint, e.g. 'repos/account/repository/tags',
                        'repos/account/repository/compare/tag_from...tag_to'
        :type endpoint: str
        :param max_attempts: Total number of attempts before giving up (including the first try). Default: 3
        :type max_attempts: int, optional
        :param backoff_factor: Used for exponential backoff delay in seconds (default: 2).
        :type backoff_factor: int, optional
        :param page_size: Number of items to request per page (default: 30, max: 100).
        :type page_size: int, optional

        :return: Parsed JSON response if successful, otherwise None
        :rtype: Optional[List[Dict]
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        self.logger.debug(f"GitHub API URL: {url}")

        for attempt in range(max_attempts):
            try:
                response = self.client.get(url, params={"per_page": page_size}, follow_redirects=True)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as ex:  # handles 4xx/5xx errors after raise_for_status()
                status_code = ex.response.status_code
                headers = ex.response.headers

                if status_code in self.retry_status_codes and attempt < max_attempts - 1:
                    wait = None

                    if "retry-after" in headers:
                        wait = int(headers["retry-after"])
                        self.logger.info(f"[Info] GitHub API: retry-after header found → waiting {wait}s")
                    elif status_code == 403 and headers.get("x-ratelimit-remaining") == "0":
                        reset_time = int(headers.get("x-ratelimit-reset", "0"))
                        now = int(time.time())
                        wait = max(0, reset_time - now)
                        self.logger.info(
                            f"[Info] GitHub API: primary rate limit reached (403) → waiting {wait}s until reset"
                        )

                    # Fallback: exponential backoff
                    if wait is None:
                        wait = backoff_factor**attempt
                        self.logger.info(f"[Info] GitHub API: no retry-after or reset header → backoff {wait}s")

                    time.sleep(wait)
                    continue
                else:
                    self.logger.error(f"[Error]: GitHub API HTTP error {status_code}: {ex}")
                    return None

            except httpx.RequestError as ex:
                self.logger.error(f"[Error]: GitHub API request error: {ex}")

                if attempt < max_attempts - 1:
                    wait = backoff_factor**attempt
                    self.logger.debug(
                        f"GitHub API: [Retry {attempt + 1}/{max_attempts}] RequestError - retrying in {wait}s"
                    )
                    time.sleep(wait)
                    continue
                else:
                    return None

        self.logger.error(f"[Error]: GitHub API: All retries failed.")
        return None

    def get_commits_between_tags(
        self, account_name: str, package_name: str, tag_from: str, tag_to: str
    ) -> Optional[List[Tuple[str, str, str]]]:
        """
        Returns a list of commits between two tags for a given GitHub project.
        Example URLs:
        - https://api.github.com/repos/torvalds/linux/compare/v6.8...v6.9

        :param account_name: GitHub account name, e.g. 'dbeaver'
        :type account_name: str
        :param package_name: Package name, e.g. 'dbeaver'
        :type package_name: str
        :param tag_from: Older tag (e.g. 'v6.8.arch1-1')
        :type tag_from: str
        :param tag_to: Newer tag (e.g. 'v6.8.arch1-2')
        :type tag_to: str
        :return: List of commit titles, their creation dates and the commit URL, or None on failure
        :rtype: Optional[List[Tuple[str, str, str]]]
        """
        endpoint = f"repos/{account_name}/{package_name}/compare/{tag_from}...{tag_to}"

        response = self.__get(endpoint)
        if response:
            return [
                (
                    commit.get("commit", {}).get("message", ""),
                    commit.get("commit", {}).get("author", {}).get("date", ""),
                    commit.get("html_url", ""),
                )
                for commit in response.get("commits", [])
            ]
        else:
            return None

    def get_package_tags(self, account_name: str, package_name: str) -> Optional[List[str]]:
        """
        Returns a list of commits between two tags for a given GitHub project.
        Example URLs:
        - https://api.github.com/repos/dbeaver/dbeaver/tags

        :param account_name: GitHub account name, e.g. 'dbeaver'
        :type account_name: str
        :param package_name: Package name, e.g. 'dbeaver'
        :type package_name: str
        :return: List of package tags, or None on failure
        :rtype: Optional[List[str]]
        """
        endpoint = f"repos/{account_name}/{package_name}/tags"

        response = self.__get(endpoint, page_size=100)
        if response:
            return [tag.get("name", "") for tag in response]
        else:
            return None

    def extract_upstream_url_information(self, upstream_url: str) -> Optional[Tuple[str, str]]:
        """
        Extracts the package repository and the project path of a given GitHub project URL and returns them.

        Example URL: https://github.com/dbeaver/dbeaver
        account: dbeaver
        package name: dbeaver

        :param upstream_url: The URL of the upstream GitHub repository
        :type upstream_url: str
        :return: A tuple containing the account name and the project name,
                or None if the URL doesn't match the expected format.
        :rtype: Optional[Tuple[str, str]]
        """
        match = re.search(r"https://github\.com/([^/]+)/([^/]+)(?:/|$)", upstream_url)

        if match:
            account_name = match.group(1)
            package_name = match.group(2)

            return account_name, package_name
        return None
