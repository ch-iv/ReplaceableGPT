import time

from .driver import Driver
from .driver import sign_in_required, CookieCache, load_cache, save_cache
from selenium.webdriver import Firefox
from loguru import logger
from typing import Optional


def validate_linkedin_url(url: str) -> bool:
    return url.startswith("https://www.linkedin.com/jobs/view/")


class LinkedinDriver(Driver):
    LOGIN_URL = (
        "https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin"
    )
    CACHE_FILENAME = "ln_cache.pickle"

    def __init__(self, config: dict[str, str]):
        self.config = config
        self.browser = Firefox()
        self._cookie_cache: Optional[CookieCache] = load_cache(self.CACHE_FILENAME)
        if self.cookie_cache and self.cookie_cache.is_valid():
            for cookie_dict in self.cookie_cache.cookies:
                self.browser.add_cookie(cookie_dict)

    def sign_in(self) -> bool:
        try:
            self.browser.get(self.LOGIN_URL)
            self.browser.find_element("id", "username").send_keys(
                self.config["LINKEDIN_USERNAME"]
            )
            self.browser.find_element("id", "password").send_keys(
                self.config["LINKEDIN_PASSWORD"]
            )
            self.browser.find_element("xpath", '//button[@type="submit"]').click()
        except Exception as e:
            logger.error(e)
            return False

        self.cookie_cache = CookieCache(self.browser.get_cookies(), time.time())
        save_cache(self.CACHE_FILENAME, self.cookie_cache)
        return True

    @property
    def cookie_cache(self) -> Optional[CookieCache]:
        return self._cookie_cache

    @cookie_cache.setter
    def cookie_cache(self, value: CookieCache):
        self._cookie_cache = value

    @sign_in_required
    def apply_to(self, url: str) -> bool:
        if not validate_linkedin_url(url):
            logger.warning(f"Invalid LinkedIn URL {url}")
            return False

        self.browser.get(url)
