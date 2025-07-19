from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAgent(ABC):
    @abstractmethod
    def run(self, query: Dict[str, Any]) -> Any:
        pass
