from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from apps.events.views import (
    EventTeamMemberViewSet,
    EventTeamViewSet,
    EventViewSet,
    LunchOptionsViewSet,
)
from apps.matches.views import TeamMatchViewSet

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='events')
router.register(r'event-teams', EventTeamViewSet, basename='event-teams')

event_team_router = routers.NestedSimpleRouter(router, r'events', lookup='event')
event_team_router.register(r'event-teams', EventTeamViewSet, basename='event-teams-nested')
event_team_router.register(
    r'lunch-options', LunchOptionsViewSet, basename='event-lunch-options-nested'
)

team_members_router = routers.NestedSimpleRouter(router, r'event-teams', lookup='event_team')
team_members_router.register(r'members', EventTeamMemberViewSet, basename='members-nested')
team_members_router.register(r'team-matches', TeamMatchViewSet, basename='team-matches-nested')

urlpatterns = [
    path('', include(event_team_router.urls)),
    path('', include(team_members_router.urls)),
]

urlpatterns += router.urls
