import httpx
import urllib.parse
from typing import Optional, List, Dict, Tuple


class GitLabAPI:
    """Handles anonymous access to the GitLab API for public data.
    Documentation: https://docs.gitlab.com/api/rest/
    """

    # A list of known repositories which do have a lot of packages
    base_urls = {"Arch": "https://gitlab.archlinux.org/api/v4"}

    def __init__(self, logger) -> None:
        """Constructor method"""
        self.logger = logger

    def __get(self, base_url: str, endpoint: str, params: Optional[Dict] = None) -> Optional[List[Dict]]:
        """Sends a GET request to the GitLab REST API.

        :param base_url: Base URL of the API, e.g. https://gitlab.archlinux.org/api/v4
        :type base_url: str
        :param endpoint: API endpoint, e.g. 'projects/:id/repository/tags'
        :type endpoint: str
        :param params: Optional parameters at the end of the URL
        :type params: Optional[Dict]
        :return: Response object if successful, otherwise None
        :rtype: Optional[List[Dict]
        """
        url = f"{base_url}/{endpoint.lstrip('/')}"

        self.logger.debug(f"GitLab API URL: {url}")

        try:
            response = httpx.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as ex:
            self.logger.error(f"[Error]: GitLab API request failed: {ex}")
            return None

    def get_commits_between_tags(
        self, base_url: str, project_path: str, tag_from: str, tag_to: str
    ) -> Optional[List[Tuple[str, str, str]]]:
        """
        Returns a list of commits between two tags for a given GitLab project.
        Example URL: https://gitlab.archlinux.org/api/v4/projects/archlinux%2Fpackaging%2Fpackages%2Fmesa/repository/compare?from=1-25.0.4-1&to=1-25.0.5-1

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
        endpoint = f"projects/{encoded_path}/repository/compare"
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
        Example URL: https://gitlab.archlinux.org/api/v4/projects/archlinux%2Fpackaging%2Fpackages%2Fmesa/repository/tags

        :param base_url: use GitLabAPI.base_urls for common types, e.g. https://gitlab.archlinux.org/api/v4
        :type base_url: str
        :param project_path: Project path, e.g. 'archlinux/packaging/packages/linux'
        :type project_path: str
        :return: List of package tags and their creation dates, or None on failure
        :rtype: Optional[List[Tuple[str, str]]]
        """
        encoded_path = urllib.parse.quote_plus(project_path)
        endpoint = f"projects/{encoded_path}/repository/tags"

        response = self.__get(base_url, endpoint)
        if response:
            return [(tag.get("name", ""), tag.get("created_at", "")) for tag in response]
        else:
            return None
