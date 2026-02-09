from rest_framework.routers import DefaultRouter

from apps.teams.views import TeamViewSet

router = DefaultRouter()

router.register('teams', TeamViewSet, basename='teams')

urlpatterns = []

urlpatterns += router.urls
