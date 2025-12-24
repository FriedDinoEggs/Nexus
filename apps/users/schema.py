from drf_spectacular.extensions import OpenApiAuthenticationExtension

from .authentication import CustomJWTAuthentication


class MyJWTSchema(OpenApiAuthenticationExtension):
    target_class = CustomJWTAuthentication
    name = 'JwtAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
