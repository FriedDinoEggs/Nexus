import logging

from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from .services import BlackListService

logger = logging.getLogger(__name__)


class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request: Request):
        result = super().authenticate(request)

        if result is None:
            return None

        token = result[1]

        if BlackListService.is_token_blacklisted(token):
            raise InvalidToken('Token has been blacklisted')

        return result
