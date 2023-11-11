from __future__ import annotations

import pickle
import time
from abc import ABC, abstractmethod
from typing import Callable, Any, Optional
from loguru import logger


class Driver(ABC):
    @abstractmethod
    def sign_in(self) -> bool:
        pass

    @property
    @abstractmethod
    def cookie_cache(self) -> CookieCache:
        pass

    @abstractmethod
    def apply_to(self, url: str) -> bool:
        pass


class CookieCache:
    def __init__(self, cookies: list[dict], last_updated: float):
        self.cookies = cookies
        self.last_updated = last_updated
        self.max_age: float = 60.0 * 60

    def is_valid(self) -> bool:
        return self.cookies and self.last_updated + self.max_age > time.time()


def load_cache(filename: str) -> Optional[CookieCache]:
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning(f"Unable to load cache\n{e}")
        return None


def save_cache(filename: str, cache: Optional[CookieCache]):
    if cache:
        with open(filename, "wb") as f:
            pickle.dump(cache, f)


def sign_in_required(func: Callable[[Driver, str], Any]):
    def wrapper(driver: Driver, url: str):
        if not driver.cookie_cache or not driver.cookie_cache.is_valid():
            driver.sign_in()
        return func(driver, url)

    return wrapper


class FormInput(ABC):
    @abstractmethod
    def to_prompt_block(self) -> str:
        pass
