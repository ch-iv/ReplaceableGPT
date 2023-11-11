from __future__ import annotations

import time
from .driver import Driver
from .driver import sign_in_required, CookieCache, load_cache, save_cache, FormInput
from selenium.webdriver import Firefox
from loguru import logger
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
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
                self.browser.execute_script(
                    "arguments[0].scrollIntoView();", submit_button[0]
                )
                logger.debug(f"Successfully sent application for: {url}")

                if (
                    self.config["DEBUG"] == "False"
                ):  # only submit in when not in debug mode
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
        text_inputs: list[LnTextInput] = self.get_text_inputs()
        for text_input in text_inputs:
            if (
                text_input.text == "Mobile phone number"
                and text_input.input.get_attribute("value")
                != self.config["PHONE_NUMBER"]
            ):
                text_input.input.clear()
                text_input.input.send_keys(self.config["PHONE_NUMBER"])
        self.get_next_button().click()

    def handle_resume_page(self):
        file_input = self.browser.find_element(By.CSS_SELECTOR, "input[type='file']")
        file_input.send_keys(self.config["RESUME_PATH"])
        self.get_next_button().click()

    def handle_additional_questions_page(self):
        all_inputs = self.get_all_inputs()
        for inp in all_inputs:
            inp.answer_default()
        self.get_next_or_review_button().click()

    def get_next_button(self):
        return self.browser.find_element(
            By.XPATH, '//button[contains(@aria-label, "Continue to next step")]'
        )

    def get_next_or_review_button(self) -> WebElement:
        """Gets either the `Next` button on a page or the `Review` button depending on which one is present."""
        try:
            return self.get_next_button()
        except NoSuchElementException:
            return self.browser.find_element(
                By.XPATH, '//button[contains(@aria-label, "Review your application")]'
            )

    def get_text_inputs(self) -> list[LnTextInput]:
        return list(
            map(
                LnTextInput,
                self.browser.find_elements(
                    By.XPATH, '//div[contains(@class, "artdeco-text-input--container")]'
                ),
            )
        )

    def get_select_inputs(self) -> list[LnSelectInput]:
        return list(
            map(
                LnSelectInput,
                self.browser.find_elements(
                    By.XPATH, '//div[@data-test-text-entity-list-form-component=""]'
                ),
            )
        )

    def get_radio_inputs(self) -> list[LnRadioInput]:
        radio_inputs = []
        for container in self.browser.find_elements(
            By.XPATH,
            '//fieldset[@data-test-form-builder-radio-button-form-component="true"]',
        ):
            radio_inputs.append(LnRadioInput(container, self.browser))
        return radio_inputs

    def get_all_inputs(self) -> list[LnTextInput | LnRadioInput | LnSelectInput]:
        all_inputs: list[LnTextInput | LnRadioInput | LnSelectInput] = []
        all_inputs.extend(self.get_text_inputs())
        all_inputs.extend(self.get_radio_inputs())
        all_inputs.extend(self.get_select_inputs())
        return all_inputs

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


class LnTextInput(FormInput):
    def __init__(self, container: WebElement):
        self.container = container
        self.label = self.container.find_element(By.XPATH, "label")
        self.text = self.label.text
        self.input = self.container.find_element(By.XPATH, "input")

    def to_prompt_block(self) -> str:
        return ""

    def answer_default(self) -> None:
        if self.input:
            self.input.send_keys("0")

    def __str__(self) -> str:
        return truncate(self.text)

    def __repr__(self):
        return self.__str__()


class LnSelectInput(FormInput):
    def __init__(self, container: WebElement):
        self.container = container
        self.label = self.container.find_element(By.XPATH, "label")
        self.text = self.label.text
        self.options: list[WebElement] = self.container.find_elements(
            By.XPATH, "select/option"
        )
        self.select = self.container.find_element(By.XPATH, "select")

    def to_prompt_block(self) -> str:
        return ""

    def answer_default(self) -> None:
        if self.select and len(self.options) > 0:
            self.select.click()
            self.options[-1].click()

    def __str__(self) -> str:
        return truncate(self.text)

    def __repr__(self):
        return self.__str__()


class LnRadioInput(FormInput):
    def __init__(self, container: WebElement, browser):
        self.container = container
        self.label = self.container.find_element(By.XPATH, "legend/span[1]/span[1]")
        self.text = self.label.text
        self.options: list[WebElement] = self.container.find_elements(
            By.XPATH, "div/input"
        )
        self.browser = browser

    def to_prompt_block(self) -> str:
        return ""

    def answer_default(self) -> None:
        if len(self.options) > 0:
            self.browser.execute_script("arguments[0].click();", self.options[-1])

    def __str__(self) -> str:
        return truncate(self.text)

    def __repr__(self):
        return self.__str__()


def truncate(text: str, max_len: int = 20) -> str:
    if len(text) < max_len:
        return text
    else:
        return text[:max_len] + "..."
