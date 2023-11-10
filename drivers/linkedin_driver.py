import time

from .driver import Driver
from .driver import sign_in_required, CookieCache, load_cache, save_cache
from selenium.webdriver import Firefox
from loguru import logger
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement


def validate_linkedin_url(url: str) -> bool:
    return url.startswith("https://www.linkedin.com/jobs/view/")


class LinkedinDriver(Driver):
    LOGIN_URL = (
        "https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin"
    )
    DUMMY_URL = "https://www.linkedin.com/psettings/guest-controls"
    CACHE_FILENAME = "ln_cache.pickle"

    def __init__(self, config: dict[str, str]):
        self.config = config
        self.browser = Firefox()
        self._cookie_cache: Optional[CookieCache] = load_cache(self.CACHE_FILENAME)
        self.set_cookie_from_cache()

    def set_cookie_from_cache(self):
        if self.cookie_cache and self.cookie_cache.is_valid():
            self.browser.get(self.DUMMY_URL)
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

        button = self.get_active_apply_button()
        if not button:
            return False

        self.browser.execute_script(
            "arguments[0].click();", button
        )  # clicking the button

    def get_active_apply_button(self) -> Optional[WebElement]:
        """Gets the easy apply button and waits for it to be enabled"""
        try:
            return WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//button[contains(@class, "jobs-apply-button") and not(contains(@class, '
                        '"artdeco-button--disabled"))]',
                    )
                )
            )
        except Exception as e:
            logger.warning(f"Couldn't get the apply button\n{e}")
            return None
