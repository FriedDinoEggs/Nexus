from drf_spectacular.utils import extend_schema
from rest_framework import permissions, viewsets

from apps.teams.serializers import TeamSerializer
from apps.users.permissions import IsEventManagerGroup, IsSuperAdminGroup

from .models import Team


@extend_schema(tags=['v1', 'Teams'])
class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    lookup_url_kwarg = 'id'

    def get_permissions(self):
        """
        Selects permissions for the current view action,
            using stricter group-based checks for mutating actions.

        Returns:
            list: A list of permission instances.
            For 'create', 'update', 'partial_update', and 'destroy' this returns a single permission
            that allows access if the user belongs to either the Super Admin or Event Manager groups
             otherwise it returns the permission list from the superclass.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [(IsSuperAdminGroup | IsEventManagerGroup)()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """
        Attach the current request user to the serializer and save the new Team instance.

        Parameters:
            serializer (rest_framework.serializers.Serializer):
                Serializer containing validated data for the object to create.
                The serializer will be saved with its `user` field set to the requesting user.
        """
        serializer.save(user=self.request.user)
