from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError
from bs4 import BeautifulSoup
import requests


class WebScraper:
    def __init__(self, logger, config: Optional[Dict[str, Any]]) -> None:
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.logger = logger
        self.config = config

    def fetch_page_content(self, url, retries=3):
        attempt = 0
        while attempt < retries:
            try:
                context = self.browser.new_context(locale="en-US")

                page = context.new_page()
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle", timeout=60000)
                content = page.content()
                return content
            except TimeoutError:
                self.logger.error(
                    f"Timeout error while fetching {url}. Retrying... [{attempt+1}/{retries}]"
                )
            except Exception as ex:
                self.logger.error(
                    f"Error while fetching {url}: {ex}. Retrying... [{attempt+1}/{retries}]"
                )
            finally:
                attempt += 1
                if attempt < retries:
                    if page:
                        page.wait_for_timeout(
                            self.config.config.get("webscraper-delay")
                        )
                        page.close()
                else:
                    page.close()

        self.logger.error(
            f"Failed to fetch content from {url} after {retries} retries."
        )
        return None

    def find_all_elements(self, content, tag=None, **kwargs):
        """
        Finds all elements in the HTML content based on the specified tag and additional attributes.

        :param content: The HTML content to be parsed.
        :param tag: The HTML tag that is being searched for (e.g. 'p', 'span', etc.).
        :param kwargs: Additional attributes that are searched for (e.g. class_, id, attrs, etc.).
        :return: A list of the elements found.
        """
        soup = BeautifulSoup(content, "html.parser")
        return soup.find_all(tag, **kwargs)

    def find_element(self, content, tag=None, **kwargs):
        """
        Finds an element in the HTML content based on the specified tag and additional attributes.

        :param content: The HTML content to be parsed.
        :param tag: The HTML tag that is being searched for (e.g. 'p', 'span', etc.).
        :param kwargs: Additional attributes that are searched for (e.g. class_, id, attrs, etc.).
        :return: A single element which was found.
        """
        soup = BeautifulSoup(content, "html.parser")
        return soup.find(tag, **kwargs)

    def check_website_availabilty(self, url: str) -> bool:
        """Checks the availability of a website by sending an HTTP GET request.
        This function sends a GET request to the specified URL and checks the HTTP status code of the response.
        If the status code is 200, it indicates that the website is reachable. Any other status code indicates
        that the website may be down or returning an error.

        :param url: The URL of the website to check.
        :type url: str
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

    def close_browser(self):
        self.browser.close()
        self.playwright.stop()
