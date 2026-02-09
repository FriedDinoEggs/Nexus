import logging

from .provider import BaseProvider, GoogleProvider, OAuthUserInfo

logger = logging.getLogger(__name__)


class SocialServices:
    @classmethod
    def _get_provider(cls, provider: str) -> BaseProvider | None:
        if 'google' == provider:
            return GoogleProvider()
        else:
            return None

    @classmethod
    def get_social_info(cls, provider: str, code: str) -> OAuthUserInfo | None:
        provider_instance: BaseProvider | None = cls._get_provider(provider)

        if provider_instance is not None:
            try:
                user_info: OAuthUserInfo = provider_instance.get_user_info(code=code)
                return user_info
            except Exception as e:
                logger.warning(f'{provider} error: {repr(e)}')

        return None
