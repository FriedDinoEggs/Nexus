from rest_framework.routers import DefaultRouter

from apps.notification.views import NotificationViewSet

router = DefaultRouter()

router.register('notification', NotificationViewSet, basename='notification')

# notification_ticket = NotificationViewSet.as_view(
#     {
#         'post': 'create',
#     }
# )
#
# urlpatterns = [re_path(r'^notification/ticket/$', notification_ticket, name='notification')]

urlpatterns = []
urlpatterns += router.urls
