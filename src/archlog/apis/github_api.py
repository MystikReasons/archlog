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
    LINK_REL = re.compile(r'<([^>]+)>;\s*rel="([^"]+)"')

    def __init__(self, logger, config, retries: int = 3, timeout: float = 10) -> None:
        """Constructor method"""
        self.logger = logger
        self.config = config

        self.client = httpx.Client(
            timeout=timeout, transport=httpx.HTTPTransport(retries=retries)
        )
        self.token = self.config.config.get("github-personal-access-token")

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
        self,
        endpoint: str,
        max_attempts: int = 3,
        backoff_factor: int = 2,
        page_size: int = 30,
    ) -> Optional[List[Dict]]:
        """Fetch all pages from the GitHub REST API using the existing retry logic.

        This method automatically handles pagination via the Link header. It also includes
        a fallback mechanism in case the Link header is missing, by checking if the
        returned data size is smaller than the requested page size.

        :param endpoint: API endpoint, e.g. 'repos/account/repository/tags',
                        'repos/account/repository/compare/tag_from...tag_to'
        :type endpoint: str
        :param max_attempts: Total number of attempts before giving up (including the first try). Default: 3
        :type max_attempts: int, optional
        :param backoff_factor: Exponential backoff delay in seconds (default: 2).
        :type backoff_factor: int, optional
        :param page_size: Number of items to request per page (default: 30, max: 100).
        :type page_size: int, optional

        :return: Parsed JSON response if successful, otherwise None
        :rtype: Optional[List[Dict]]
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        results = []
        request_headers = (
            {"Authorization": f"Bearer {self.token}"} if self.token else {}
        )
        request_params = {"per_page": page_size}
        page_number = 1
        max_pages = 8

        while url and (page_number <= max_pages):
            self.logger.debug(f"[Debug] Fetching page {page_number}: {url}")
            data, headers = self.__get_single_page(
                url, request_headers, request_params, max_attempts, backoff_factor
            )

            if not data:
                self.logger.error(
                    f"[Error] Failed to fetch page {page_number}. Aborting pagination."
                )
                return None

            # list - when the API returns package tags
            # dict - when the API returns package commits
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)

            self.logger.debug(
                f"[Debug] Page {page_number} fetched, {len(data)} items returned, total so far: {len(results)}"
            )

            # Check the Link header for the next page
            link_header = headers.get("Link")
            next_url = None
            if link_header:
                self.logger.debug(f"[Debug] Link header: {link_header}")
                for match in self.LINK_REL.finditer(link_header):
                    link_url, rel = match.groups()
                    if rel == "next":
                        next_url = link_url
                        break

            # Fallback: if no Link header and page is smaller than page_size -> end reached
            if next_url is None and len(data) < page_size:
                self.logger.debug(
                    f"[Debug] Last page reached (less than {page_size} items)."
                )
                break

            url = next_url
            request_params = None  # For page 2+ already in URL
            page_number += 1

        return results

    def __get_single_page(
        self,
        url: str,
        headers: Dict,
        params: Dict,
        max_attempts: int,
        backoff_factor: int,
    ):
        """Fetch a single page from GitHub with retry logic for rate limits and transient errors.

        If a retryable HTTP status code is returned (e.g., 429, 500, 502, 503, 504, see GitHubAPI.retry_status_codes),
        the method retries the request up to 'max_attempts' times. The delay between attempts is determined as follows:

            1. If the 'retry-after' header is present, wait for the specified number of seconds.
            2. If 'x-ratelimit-remaining' is 0 and 'x-ratelimit-reset' is present, wait until the reset time.
            3. Otherwise, fall back to exponential backoff:

                wait = backoff_factor ** attempt_number

        For example, with a 'backoff_factor' of 2, wait times would be:
        1s (first retry), 2s, 4s, 8s, etc.

        :param url: The API URL to request
        :type url: str
        :param headers: Query headers (e.g., authorization token)
        :type headers: dict
        :param params: Query parameters (e.g., per_page)
        :type params: dict
        :param max_attempts: Total number of attempts before giving up (including the first try).
        :type max_attempts: int
        :param backoff_factor: Exponential backoff delay in seconds.
        :type backoff_factor: int
        :return: Tuple of (JSON data, response headers) or (None, {}) on failure
        :rtype: Tuple[List, Dict]
        """
        for attempt in range(max_attempts):
            try:
                response = self.client.get(
                    url, headers=headers, params=params, follow_redirects=True
                )
                response.raise_for_status()
                return response.json(), response.headers

            except (
                httpx.HTTPStatusError
            ) as ex:  # handles 4xx/5xx errors after raise_for_status()
                status_code = ex.response.status_code
                headers = ex.response.headers

                if (
                    status_code in self.retry_status_codes
                    and attempt < max_attempts - 1
                ):
                    wait = None

                    if "retry-after" in headers:
                        wait = int(headers["retry-after"])
                        self.logger.info(
                            f"[Info] GitHub API: retry-after header found -> waiting {wait}s"
                        )
                    elif (
                        status_code == 403
                        and headers.get("x-ratelimit-remaining") == "0"
                    ):
                        reset_time = int(headers.get("x-ratelimit-reset", "0"))
                        now = int(time.time())
                        wait = max(0, reset_time - now)
                        self.logger.info("[Info] GitHub API:")
                        self.logger.info(
                            f"primary rate limit reached (403) -> waiting {wait}s until reset"
                        )
                        self.logger.info(
                            "Note: You can avoid this wait by using a classical Personal Access Token (GITHUB_TOKEN),"
                        )
                        self.logger.info(
                            "which raises the limit to 5000 requests per hour instead of 60 requests per hour."
                        )
                        self.logger.info(
                            "Copy and paste the created token into the field 'github-personal-access-token' in the config file."
                        )
                        self.logger.info(
                            "Create your personal token here: https://github.com/settings/tokens"
                        )

                    # Fallback: exponential backoff
                    if wait is None:
                        wait = backoff_factor**attempt
                        self.logger.info(
                            f"[Info] GitHub API: no retry-after or reset header -> backoff {wait}s"
                        )

                    time.sleep(wait)
                    continue
                else:
                    self.logger.error(
                        f"[Error]: GitHub API HTTP error {status_code}: {ex}"
                    )
                    return None, {}

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
                    return None, {}

        self.logger.error(f"[Error]: GitHub API: All retries failed.")
        return None, {}

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

        response = self.__get(endpoint, page_size=100)
        all_commits = []
        if response:
            for page in response:
                commits = page.get("commits", [])
                for commit in commits:
                    all_commits.append(
                        (
                            commit.get("commit", {}).get("message", ""),
                            commit.get("commit", {}).get("author", {}).get("date", ""),
                            commit.get("html_url", ""),
                        )
                    )
            return all_commits
        else:
            return None

    def get_package_tags(
        self, account_name: str, package_name: str
    ) -> Optional[List[str]]:
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

    def extract_upstream_url_information(
        self, upstream_url: str
    ) -> Optional[Tuple[str, str]]:
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
