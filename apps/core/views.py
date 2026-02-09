from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status, views
from rest_framework.permissions import AllowAny
from rest_framework.views import Response


@extend_schema(tags=['v1', 'Core'])
class health(views.APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: OpenApiTypes.NONE},
        methods=['GET'],
        auth=[],
    )
    def get(self, request):
        return Response(status=status.HTTP_200_OK)

    @extend_schema(
        responses={200: OpenApiTypes.NONE},
        methods=['HEAD'],
        auth=[],
    )
    def head(self, request):
        return Response(status=status.HTTP_200_OK)
