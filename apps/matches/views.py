from django.db.models import Q
from rest_framework import permissions, viewsets

from apps.users.permissions import IsEventManagerGroup, IsSuperAdminGroup

from .models import MatchTemplate, TeamMatch
from .serializers import MatchTemplateSerializer, TeamMatchSerializer


class MatchTemplateViewSet(viewsets.ModelViewSet):
    queryset = MatchTemplate.objects.all().prefetch_related('items')
    serializer_class = MatchTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [(IsSuperAdminGroup | IsEventManagerGroup)()]
        return super().get_permissions()


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
