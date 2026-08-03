from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notification.services.services import NotificationServices

# Create your views here.


class NotificationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['POST'], url_path='ticket')
    def ticket(self, request):
        NotificationServices.send_init_notifications(request.user.id)
        return Response({'ticket': f'{NotificationServices.gen_ticket(request.user.id)}'})
