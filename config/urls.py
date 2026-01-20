"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# from django.db.models import lookups
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from apps.events.views import (
    EventTeamMemberViewSet,
    EventTeamViewSet,
    EventViewSet,
    LunchOptionsViewSet,
    # EventTeamEnrollViewSet,
)
from apps.teams.views import TeamViewSet

router = DefaultRouter()
router.register(r'teams', TeamViewSet, basename='teams')
router.register(r'events', EventViewSet, basename='events')
router.register(r'event-teams', EventTeamViewSet, basename='event-teams')

event_team_router = routers.NestedSimpleRouter(router, r'events', lookup='event')
event_team_router.register(r'event-teams', EventTeamViewSet, basename='event-teams-nested')
event_team_router.register(
    r'lunch-options', LunchOptionsViewSet, basename='event-lunch-options-nested'
)

team_members_router = routers.NestedSimpleRouter(router, r'event-teams', lookup='event_team')
team_members_router.register(r'members', EventTeamMemberViewSet, basename='members-nested')


# router.register(r'Team_match', TeamMatchViewSet, basename='team_match')

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'api/v1/',
        include(
            (
                [
                    path(
                        'users/', include(('apps.users.urls', 'users_app'), namespace='users_app')
                    ),
                    path('', include(router.urls)),
                    path('', include(event_team_router.urls)),
                    path('', include(team_members_router.urls)),
                    # path('', include(event_team_enroll_router.urls)),
                ],
                'v1',
            ),
            namespace='v1',
        ),
    ),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/schema/swagger-ui/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
]
