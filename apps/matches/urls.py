from rest_framework.routers import DefaultRouter

from apps.matches.views import MatchTemplateViewSet, TeamMatchViewSet

router = DefaultRouter()

router.register('match-template', MatchTemplateViewSet, basename='match-template')
router.register('team-matches', TeamMatchViewSet, basename='team-matches')

urlpatterns = []
urlpatterns += router.urls
