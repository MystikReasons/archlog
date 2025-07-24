from pathlib import Path
import subprocess
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
import httpx
import sys


class WebScraper:
    def __init__(self, logger, config: Optional[Dict[str, Any]]) -> None:
        """Constructor method"""
        self.logger = logger
        self.config = config

    def fetch_page_content(self, url: str, retries: int = 3) -> Optional[str]:
        """Fetches the full HTML content of a page using an HTTP GET request with httpx with retry logic.

        This function sends a GET request to the specified URL and returns the response as text.
        It retries the request on timeout or other errors, up to the specified number of attempts.

        :param url: The target URL to fetch content from.
        :type url: str
        :param retries: Number of retry attempts in case of failure.
        :type retries: int
        :return: HTML content of the page as a string, or None if all attempts fail.
        :rtype: Optional[str]
        """
        attempt = 0
        while attempt < retries:
            try:
                response = httpx.get(url, follow_redirects=True, timeout=self.config.config.get("webscraper-delay"))
                response.raise_for_status()
                return response.text
            except Exception as ex:
                self.logger.debug(f"[Debug]: HTTP exception for {url} - Error code: {ex}")
            finally:
                attempt += 1

        self.logger.error(
            f"""[Error]: Failed to fetch content from {url} after {retries} retries. Please check the logs for further information."""
        )
        return None

    def find_all_elements(self, content: str, tag: Optional[str] = None, **kwargs: Any) -> List:
        """Finds all elements in the HTML content based on the specified tag and additional attributes.

        :param content: The HTML content to be parsed.
        :type content: str
        :param tag: The HTML tag that is being searched for (e.g. 'p', 'span', etc.).
        :type tag: Optional[str]
        :param kwargs: Additional attributes that are searched for (e.g. class_, id, attrs, etc.).
        :type kwargs: Any
        :return: A list of matched elements.
        :rtype: List
        """
        soup = BeautifulSoup(content, "html.parser")
        return soup.find_all(tag, **kwargs)

    def find_element(self, content: str, tag: Optional[str] = None, **kwargs: Any) -> Optional:
        """Finds an element in the HTML content based on the specified tag and additional attributes.

        :param content: The HTML content to be parsed.
        :type content: str
        :param tag: The HTML tag that is being searched for (e.g. 'p', 'span', etc.).
        :type tag: Optional[str]
        :param kwargs: Additional attributes that are searched for (e.g. class_, id, attrs, etc.).
        :type kwargs: Any
        :return: The first matched element or None if no match is found.
        :rtype: Optional
        """
        soup = BeautifulSoup(content, "html.parser")
        return soup.find(tag, **kwargs)

    def find_elements_between_two_elements(
        self, content: str, row_designator: str, start_element: str, end_element: str
    ) -> List:
        """Finds all elements between two specified text markers within the given HTML content.

        Parses the HTML and collects all elements matching the row_designator that appear
        after the start_element and before the end_element.

        :param content: The HTML content to be parsed.
        :type content: str
        :param row_designator: Tag name used to select rows (e.g. 'tr', 'div').
        :type row_designator: str
        :param start_element: Text content that marks the start of the selection.
        :type start_element: str
        :param end_element: Text content that marks the end of the selection.
        :type end_element: str
        :return: List of elements found between the start and end markers.
        :rtype: List
        """
        soup = BeautifulSoup(content, "html.parser")
        rows = soup.find_all(row_designator)

        start_collecting = False
        result_rows = []

        for row in rows:
            if not start_collecting and row.find(string=start_element):
                start_collecting = True

            if start_collecting and row.find(string=end_element):
                break

            if start_collecting:
                result_rows.append(row)

        return result_rows

    def check_website_availabilty(self, url: str) -> bool:
        """Checks the availability of a website by sending an HTTP GET request with httpx.
        This function sends a GET request to the specified URL and checks the HTTP status code of the response.
        If the status code is 2xx, it indicates that the website is reachable. Any other status code indicates
        that the website may be down or returning an error.

        :param url: The URL of the website to check.
        :type url: str
        :return: True if the website is reachable (status code 200), otherwise False.
        :rtype: bool
        """
        try:
            response = httpx.get(url, follow_redirects=True)
            response.raise_for_status()  # Raise an exception for any response which are not 2xx success code
            self.logger.info(f"[Info]: Website: {url} is reachable")
            return True
        except httpx.HTTPError as ex:
            self.logger.debug(f"[Debug]: HTTP exception for {url} - Error code: {ex}")
            return False
