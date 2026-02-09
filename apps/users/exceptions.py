class ProviderBaseException(Exception):
    code = 'Provider_error'
    message = 'unknown error'

    def __init__(self, message=None, code=None):
        self.message = message or self.message
        self.code = code or self.code
        super().__init__(self.message)


class ProviderNotFoundError(ProviderBaseException):
    code = 'PROVIDER_NOT_SUPPORTED'
    message = 'unsupported social platform provider'


class ProviderInvalidTokenError(ProviderBaseException):
    code = 'INVALID_SOCIAL_TOKEN'
    message = 'social platform token validated error or expired'
