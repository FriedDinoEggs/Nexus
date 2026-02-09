from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, viewsets

from apps.users.permissions import IsEventManagerGroup

from .models import TeamMatch
from .serializers import TeamMatchSerializer


@extend_schema(
    tags=['v1', 'Matches'],
    parameters=[
        OpenApiParameter(
            name='event_team_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description='其中一隊伍的 ID',
        ),
    ],
)
class TeamMatchViewSet(viewsets.ModelViewSet):
    queryset = (
        TeamMatch.objects.all()
        .select_related('team_a__team', 'team_b__team')
        .prefetch_related('player_matches__participants__player')
    )
    serializer_class = TeamMatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        event_team_pk = self.kwargs.get('event_team_id')
        if event_team_pk:
            queryset = queryset.filter(Q(team_a_id=event_team_pk) | Q(team_b_id=event_team_pk))
        return queryset

    def get_permissions(self):
        if self.action not in permissions.SAFE_METHODS:
            return [IsEventManagerGroup()]
        else:
            return super().get_permissions()
