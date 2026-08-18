from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notification.models import Notification
from apps.notification.services.services import NotificationServices

# Create your views here.


class NotificationViewSet(
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Notification.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(deleted_at=None)

        user = self.request.user
        user_group_name = user.groups.values_list('name', flat=True)

        if 'SuperAdmin' in user_group_name:
            return qs
        elif 'EventManager' in user_group_name:
            return qs.filter(user=user)
        elif 'Member' in user_group_name:
            return qs.filter(user=user)

    @action(detail=False, methods=['POST'], url_path='ticket')
    def ticket(self, request):
        # NotificationServices.send_init_notifications(request.user.id)
        return Response({'ticket': f'{NotificationServices.gen_ticket(request.user.id)}'})

    @action(detail=True, methods=['POST'], url_path='mark_read')
    def mark_read(self, request):
        notificaion = self.get_object()
        notificaion.status = Notification.Status.READ
        notificaion.save()

        return Response({'status': 'notification marked as read'})

    @action(detail=True, methods=['POST'], url_path='mark_unread')
    def mark_unread(self, request):
        notificaion = self.get_object()
        notificaion.status = Notification.Status.UNREAD
        notificaion.save()

        return Response({'status': 'notification marked as read'})

    def perform_destroy(self, instance) -> None:
        instance.status = Notification.Status.DELETED
        return super().perform_destroy(instance)
