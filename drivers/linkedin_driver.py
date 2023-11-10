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

        # Iterate over every page of the application and handle
        # each page using a custom strategy based on the page_title.
        # `max_pages` is used to break the while loop if the submit
        # button is never reached.
        max_pages = 1000
        current_pages = 0
        while current_pages < max_pages:
            current_pages += 1

            submit_button: list[WebElement] = self.browser.find_elements(
                By.XPATH, '//button[contains(@aria-label, "Submit application")]'
            )
            if len(submit_button) > 0:
                submit_button[0].click()
                break

            page_title = self.browser.find_element(
                By.XPATH, '//h3[contains(@class, "t-16")]'
            )
            if not page_title:
                logger.warning("Couldn't get page title")
                return False

            match page_title.text:
                case "Contact info":
                    self.handle_contact_info_page()
                case "Resume":
                    self.handle_resume_page()
                case "Additional Questions":
                    self.handle_additional_questions_page()
                case _:
                    logger.warning(f"Unknown page title: {page_title.text}")

        return True

    def handle_contact_info_page(self):
        input_containers = self.get_text_inputs()
        for input_container in input_containers:
            label = input_container.find_element(By.TAG_NAME, "label")
            input_tag = input_container.find_element(By.TAG_NAME, "input")
            if label.text == "Mobile phone number":
                if input_tag.get_attribute("value") != self.config["PHONE_NUMBER"]:
                    input_tag.clear()
                    input_tag.send_keys(self.config["PHONE_NUMBER"])
        next_button = self.browser.find_element(
            By.XPATH, '//button[contains(@aria-label, "Continue to next step")]'
        )
        next_button.click()

    def handle_resume_page(self):
        pass

    def handle_additional_questions_page(self):
        pass

    def get_text_inputs(self) -> list[WebElement]:
        return self.browser.find_elements(
            By.XPATH, '//div[contains(@class, "artdeco-text-input--container")]'
        )

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
