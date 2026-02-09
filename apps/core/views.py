from rest_framework import status, views
from rest_framework.permissions import AllowAny
from rest_framework.views import Response


class health(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=status.HTTP_200_OK)
