from rest_framework.routers import DefaultRouter

from apps.matches.views import TeamMatchViewSet

router = DefaultRouter()

router.register('team-matches', TeamMatchViewSet, basename='team-matches')

urlpatterns = []
urlpatterns += router.urls
