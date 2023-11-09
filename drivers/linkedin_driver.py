from .driver import Driver
from selenium.webdriver import Firefox
from loguru import logger


def validate_linkedin_url(url: str) -> bool:
    return url.startswith("https://www.linkedin.com/jobs/view/")


class LinkedinDriver(Driver):
    LOGIN_URL = (
        "https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin"
    )

    def __init__(self, config: dict[str, str]):
        self.config = config
        self.browser = Firefox()

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
        return True

    def apply_to(self, url: str) -> bool:
        if not validate_linkedin_url(url):
            logger.warning(f"Invalid LinkedIn URL {url}")
            return False

        self.browser.get(url)
