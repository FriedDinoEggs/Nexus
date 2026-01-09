from django.contrib.auth import get_user_model
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import Response

from apps.users.permissions import (
    IsEventManagerGroup,
    IsOwnerObject,
    IsSuperAdminGroup,
)

from .models import Event, EventTeam, EventTeamMember, LunchOption
from .serializers import (
    EventSerializer,
    EventTeamMemberSerializer,
    EventTeamSerializer,
    LunchOptionSerializer,
)
from .services import EventService

User = get_user_model()


class EventViewSet(viewsets.ModelViewSet):
    queryset = (
        Event.objects.all()
        .select_related('location')
        .prefetch_related('teams', 'event_teams', 'lunch_options')
    )
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]

    lookup_url_kwarg = 'id'

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [(IsEventManagerGroup | IsSuperAdminGroup)()]
        return super().get_permissions()


class LunchOptionsViewSet(viewsets.ModelViewSet):
    queryset = LunchOption.objects.all().select_related('event')
    serializer_class = LunchOptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    lookup_url_kwarg = 'id'

    def get_queryset(self):
        queryset = super().get_queryset()

        event_id = self.kwargs.get('event_id')
        if event_id:
            queryset = queryset.filter(event_id=event_id)

        return queryset

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [(IsEventManagerGroup | IsSuperAdminGroup)()]

        return super().get_permissions()

    def perform_create(self, serializer) -> None:
        event_id_nested = self.kwargs.get('event_id', None)
        if event_id_nested:
            event = Event.objects.get(pk=event_id_nested)
            serializer.save(event=event)
        else:
            serializer.save()


class EventTeamViewSet(viewsets.ModelViewSet):
    queryset = EventTeam.objects.all().select_related('event', 'team', 'coach', 'leader')
    serializer_class = EventTeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    lookup_url_kwarg = 'id'

    def get_queryset(self):
        queryset = super().get_queryset()

        event_id = self.kwargs.get('event_id')

        if event_id:
            queryset = queryset.filter(event_id=event_id)

        return queryset

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [(IsEventManagerGroup | IsSuperAdminGroup)()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs) -> Response:
        data = request.data.copy()

        event_id_url = self.kwargs.get('event_id')

        if event_id_url:
            data['event'] = event_id_url

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        header = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=header)

    @action(detail=False, methods=['GET'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        queryset = super().get_queryset()
        queryset = queryset.filter(roster__user=self.request.user)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class EventTeamMemberViewSet(viewsets.ModelViewSet):
    queryset = (
        EventTeamMember.objects.all()
        .select_related('event_team__event', 'event_team__team', 'user')
        .prefetch_related('lunch_orders__option')
    )
    serializer_class = EventTeamMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    lookup_url_kwarg = 'id'

    def get_permissions(self):
        # 只開放 list / create / destroy 給 MemberGroup 顯示使用
        if self.action in ['retrieve', 'update', 'partial_update', 'create', 'destroy']:
            return [(IsSuperAdminGroup | IsEventManagerGroup | IsOwnerObject)()]

        # list create
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()

        event_id = self.kwargs.get('event_id')
        event_team_id = self.kwargs.get('event_team_id')

        if event_team_id:
            filters = {'event_team_id': event_team_id}
            if event_id:
                filters['event_team__event_id'] = event_id
            queryset = queryset.filter(**filters)

        user_param = self.request.query_params.get('user')
        if user_param:
            if user_param == 'me':
                queryset = queryset.filter(user=self.request.user)
            else:
                queryset = queryset.filter(user=user_param)

        return queryset

    def create(self, request, *args, **kwargs):
        user = None
        data = request.data.copy()

        user_params = request.data.get('user', None)

        if user_params:
            is_privileged = EventService.is_privileged(user=request.user)

            if is_privileged:
                user = user_params

        if not user:
            user = self.request.user.id

        data['event_team'] = self.kwargs.get('event_team_id')
        data['user'] = user
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()
