import logging

from django.conf import settings
from google.auth.transport import requests as google_request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from apps.users.exceptions import ProviderInvalidTokenError

from .base import BaseProvider, OAuthUserInfo

logger = logging.getLogger(__name__)


class GoogleProvider(BaseProvider):
    def get_user_info(self, code) -> OAuthUserInfo:
        flow = Flow.from_client_secrets_file(
            settings.GOOGLE_OAUTH_SECRET_FILE_PATH,
            scopes=[
                'openid',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/userinfo.email',
            ],
            redirect_uri='postmessage',
        )

        try:
            flow.fetch_token(code=code)

            credential = flow.credentials

            id_info = id_token.verify_oauth2_token(
                credential.id_token,
                google_request.Request(),
                settings.GOOGLE_WEB_CLIENT_ID,
            )

            return OAuthUserInfo(
                provider='google',
                provider_user_id=id_info['sub'],
                email=id_info['email'],
                full_name=id_info.get('name', ''),
            )
        except Exception as e:
            logger.error(f'get info from google api error {e}', exc_info=True)
            raise ProviderInvalidTokenError from None
