from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError
from bs4 import BeautifulSoup

class WebScraper:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)

    def fetch_page_content(self, url, retries=3, delay=15000):
        attempt = 0
        while attempt < retries:
            try:
                page = self.browser.new_page()
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle", timeout=60000)
                content = page.content()
                return content
            except TimeoutError:
                self.logger.error(f"Timeout error while fetching {url}. Retrying... [{attempt+1}/{retries}]")
            except Exception as ex:
                self.logger.error(f"Error while fetching {url}: {ex}. Retrying... [{attempt+1}/{retries}]")
            finally:
                attempt += 1
                if attempt < retries:
                    if page:
                        page.wait_for_timeout(delay)
                        page.close()
                else:
                    page.close()
                
        
        self.logger.error(f"Failed to fetch content from {url} after {retries} retries.")
        return None

    def find_all_elements(self, content, tag=None, **kwargs):
        """
        Finds all elements in the HTML content based on the specified tag and additional attributes.

        :param content: The HTML content to be parsed.
        :param tag: The HTML tag that is being searched for (e.g. 'p', 'span', etc.).
        :param kwargs: Additional attributes that are searched for (e.g. class_, id, attrs, etc.).
        :return: A list of the elements found.
        """
        soup = BeautifulSoup(content, 'html.parser')
        return soup.find_all(tag, **kwargs)

    def find_element(self, content, tag=None, **kwargs):
        """
        Finds an element in the HTML content based on the specified tag and additional attributes.

        :param content: The HTML content to be parsed.
        :param tag: The HTML tag that is being searched for (e.g. 'p', 'span', etc.).
        :param kwargs: Additional attributes that are searched for (e.g. class_, id, attrs, etc.).
        :return: A single element which was found.
        """
        soup = BeautifulSoup(content, 'html.parser')
        return soup.find(tag, **kwargs)

    def close_browser(self):
        self.browser.close()
        self.playwright.stop()