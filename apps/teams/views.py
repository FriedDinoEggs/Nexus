from rest_framework import permissions, viewsets

from apps.teams.serializers import TeamSerializer
from apps.users.permissions import IsEventManagerGroup, IsSuperAdminGroup

from .models import Team


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    lookup_url_kwarg = 'id'

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [(IsSuperAdminGroup | IsEventManagerGroup)()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
