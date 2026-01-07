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

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [(IsSuperAdminGroup | IsEventManagerGroup)()]
        return super().get_permissions()
