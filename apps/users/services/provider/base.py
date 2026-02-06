from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    provider: str
    provider_user_id: str
    email: str
    full_name: str


class BaseProvider(ABC):
    @abstractmethod
    def get_user_info(self, code) -> OAuthUserInfo:
        pass
