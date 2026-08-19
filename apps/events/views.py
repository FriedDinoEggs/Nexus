from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.views import Response

from apps.notification.models import Notification
from apps.notification.services.services import NotificationServices
from apps.teams.services import TeamService
from apps.users.permissions import (
    IsEventManagerGroup,
    IsOwnerObject,
    IsSuperAdminGroup,
)

from .models import (
    Event,
    EventAttachments,
    EventFavorites,
    EventMatchTemplate,
    EventTeam,
    EventTeamMember,
    LunchOption,
)
from .serializers import (
    EventAttachmentSerializer,
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
        .prefetch_related('teams', 'event_teams', 'lunch_options', 'event_attachments')
    )
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]

    lookup_url_kwarg = 'id'

    @action(detail=True, methods=['post', 'delete'], url_path='favorite')
    def favorite(self, request, id=None):
        event = self.get_object()
        user = request.user

        if request.method == 'POST':
            EventFavorites.objects.get_or_create(user=user, event=event)
            return Response({'detail': 'Add to favorites'}, status=status.HTTP_200_OK)

        elif request.method == 'DELETE':
            EventFavorites.objects.filter(user=user, event=event).delete()
            return Response({'detail': 'Removed from favorites'}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['get'],
        url_path='favorites',
        permission_classes=[permissions.IsAuthenticated],
    )
    def favorites(self, request):
        user = request.user

        favorite_events = Event.objects.filter(favorites=user)
        page = self.paginate_queryset(favorite_events)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(favorite_events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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

    def perform_update(self, serializer):
        event = serializer.save()
        updated_fields = serializer.validated_data.keys()
        if any(f in updated_fields for f in ['start_time', 'end_time', 'location']):
            member_user_ids = list(
                EventTeamMember.objects.filter(event_team__event=event)
                .values_list('user_id', flat=True)
                .distinct()
            )
            favorite_user_ids = list(event.favorites.values_list('id', flat=True).distinct())
            all_user_ids = set(member_user_ids + favorite_user_ids)
            for uid in all_user_ids:
                NotificationServices.send_notification(
                    user_id=uid,
                    title='【緊急賽程異動】請注意地點與時間',
                    body=f'賽事「{event.name}」的地點或時間已緊急變更，請立即至賽事頁面確認！',
                    payload={'event_id': event.id, 'event_name': event.name},
                    type=Notification.Type.ALERT,
                )

    def perform_destroy(self, instance):
        event_name = instance.name
        event_id = instance.id
        member_user_ids = list(
            EventTeamMember.objects.filter(event_team__event=instance)
            .values_list('user_id', flat=True)
            .distinct()
        )
        favorite_user_ids = list(instance.favorites.values_list('id', flat=True).distinct())
        all_user_ids = set(member_user_ids + favorite_user_ids)

        super().perform_destroy(instance)

        for uid in all_user_ids:
            NotificationServices.send_notification(
                user_id=uid,
                title='【緊急通知】賽事已被取消',
                body=f'您報名的賽事「{event_name}」已被管理員取消，請注意最新公告！',
                payload={'event_id': event_id, 'event_name': event_name},
                type=Notification.Type.ALERT,
            )


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

    def perform_update(self, serializer):
        old_status = self.get_object().status
        event_team = serializer.save()
        new_status = event_team.status
        if old_status != new_status and new_status in [
            EventTeam.StatusChoices.APPROVED,
            EventTeam.StatusChoices.REJECT,
        ]:
            status_text = '通過審核' if new_status == EventTeam.StatusChoices.APPROVED else '退回'
            recipients = set()
            if event_team.leader:
                recipients.add(event_team.leader.id)
            if event_team.coach:
                recipients.add(event_team.coach.id)
            if event_team.team and event_team.team.leader:
                recipients.add(event_team.team.leader.id)
            for uid in recipients:
                NotificationServices.send_notification(
                    user_id=uid,
                    title='【隊伍報名審核結果】',
                    body=f'您的隊伍「{event_team.team.name}」在「{event_team.event.name}」的報名申請已{status_text}。',
                    payload={'event_team_id': event_team.id, 'status': new_status},
                    type=Notification.Type.SYSTEM_INFO,
                )

    def perform_destroy(self, instance):
        team_name = instance.team.name if instance.team else '隊伍'
        event_name = instance.event.name if instance.event else '賽事'
        event_team_id = instance.id

        recipients = set(instance.event_team_members.values_list('user_id', flat=True).distinct())
        if instance.leader:
            recipients.add(instance.leader.id)
        if instance.coach:
            recipients.add(instance.coach.id)
        if instance.team and instance.team.leader:
            recipients.add(instance.team.leader.id)

        super().perform_destroy(instance)

        for uid in recipients:
            NotificationServices.send_notification(
                user_id=uid,
                title='【隊伍報名取消告警】',
                body=f'您的隊伍「{team_name}」在賽事「{event_name}」的隊伍報名已被取消。',
                payload={
                    'event_team_id': event_team_id,
                    'team_name': team_name,
                    'event_name': event_name,
                },
                type=Notification.Type.ALERT,
            )

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

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs[lookup_url_kwarg]

        if lookup_value == 'me':
            queryset = self.filter_queryset(self.get_queryset())
            obj = get_object_or_404(queryset, user=self.request.user)
            self.check_object_permissions(self.request, obj)
            return obj

        return super().get_object()

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

    def perform_create(self, serializer) -> None:
        instance = serializer.save()
        instance_data = dict(EventTeamMemberSerializer(instance).data)
        event_name = instance.event_team.event.name
        if instance.status == EventTeamMember.Status.WAITLIST:
            title = '【報名候補通知】'
            body = f'您已列入「{event_name}」的候補名單。'
        else:
            title = '【報名成功通知】'
            body = f'您已成功報名參加「{event_name}」。'

        NotificationServices.send_notification(
            user_id=instance.user.id,
            title=title,
            body=body,
            payload=instance_data,
            type=Notification.Type.SYSTEM_INFO,
        )

    def perform_destroy(self, instance) -> None:
        event_team = instance.event_team
        event_name = event_team.event.name
        was_regular = instance.status == EventTeamMember.Status.REGULAR
        user_id = instance.user.id

        super().perform_destroy(instance)

        NotificationServices.send_notification(
            user_id=user_id,
            title='【取消報名通知】',
            body=f'您已成功取消報名「{event_name}」。',
            payload={},
            type=Notification.Type.SYSTEM_INFO,
        )

        if was_regular:
            next_wl = (
                event_team.event_team_members.filter(status=EventTeamMember.Status.WAITLIST)
                .order_by('created_at')
                .first()
            )
            if next_wl:
                next_wl.status = EventTeamMember.Status.REGULAR
                next_wl.save()
                next_data = dict(EventTeamMemberSerializer(next_wl).data)
                NotificationServices.send_notification(
                    user_id=next_wl.user.id,
                    title='【備取遞補成功】',
                    body=f'您已成功遞補為「{event_name}」的正式參賽選手！',
                    payload=next_data,
                    type=Notification.Type.SYSTEM_INFO,
                )


class EventAttachmentViewSet(viewsets.ModelViewSet):
    queryset = EventAttachments.objects.all()
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    serializer_class = EventAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdminGroup | IsEventManagerGroup]
