from abc import ABC, abstractmethod


class Driver(ABC):
    @abstractmethod
    def apply_to(self, url: str) -> bool:
        pass
