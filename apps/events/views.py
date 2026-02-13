from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import Response

from apps.teams.services import TeamService
from apps.users.permissions import (
    IsEventManagerGroup,
    IsOwnerObject,
    IsSuperAdminGroup,
)

from .models import Event, EventMatchTemplate, EventTeam, EventTeamMember, LunchOption
from .serializers import (
    EventCalendarSerializer,
    EventMatchTemplateSerializer,
    EventSerializer,
    EventTeamMemberSerializer,
    EventTeamSerializer,
    LunchOptionSerializer,
)
from .services import EventService

User = get_user_model()


@extend_schema(tags=['v1', 'Events'])
class MatchTemplateViewSet(viewsets.ModelViewSet):
    queryset = EventMatchTemplate.objects.all().prefetch_related('items')

    serializer_class = EventMatchTemplateSerializer

    permission_classes = [permissions.IsAuthenticated]

    lookup_url_kwarg = 'id'

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [(IsSuperAdminGroup | IsEventManagerGroup)()]

        return super().get_permissions()


@extend_schema(tags=['v1', 'Events'])
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

    def get_queryset(self):
        if self.request.query_params.get('calendar') == 'true':
            qs = Event.objects.all()
            start = self.request.query_params.get('start')
            end = self.request.query_params.get('end')
            if start and end:
                qs = qs.filter(Q(start_time__lt=end) & Q(end_time__gt=start))
            qs = qs.only('id', 'name', 'start_time', 'end_time')
            return qs
        return super().get_queryset()

    def get_serializer_class(self):
        if self.request.query_params.get('calendar') == 'true':
            return EventCalendarSerializer
        return super().get_serializer_class()

    @property
    def paginator(self):
        if self.request.query_params.get('calendar') == 'true':
            return None
        return super().paginator


@extend_schema(tags=['v1', 'Events'])
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
            try:
                event = Event.objects.get(pk=event_id_nested)
            except Exception as e:
                raise serializers.ValidationError(
                    {'event_id': f'event_id: {event_id_nested} not found', 'detail': f'{str(e)}'}
                ) from None
            serializer.save(event=event)
        else:
            serializer.save()


@extend_schema(tags=['v1', 'Events'])
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

        if not data.get('team'):
            new_team_name = data.get('new_team_name')
            if not new_team_name:
                raise serializers.ValidationError(
                    'Either team:id or new_team_name:str field must be provided.'
                )
            try:
                team = TeamService.create_team(user=request.user, name=new_team_name)
                data['team'] = team.id
                del data['new_team_name']
            except Exception as e:
                raise serializers.ValidationError({'detail': str(e)}) from None

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        header = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=header)

    @action(detail=False, methods=['GET'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        queryset = super().get_queryset()
        queryset = queryset.filter(event_team_members__user=self.request.user)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema(tags=['v1', 'Events'])
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
