import json
import logging
import uuid
from datetime import timedelta

import django_redis
from django.utils import timezone

from apps.events.models import Event
from apps.events.serializers import EventSerializer
from apps.notification.models import Notification, NotificationLog
from apps.notification.serializers import NotificationSerializer

logger = logging.getLogger(__name__)


class NotificationServices:
    @staticmethod
    def gen_ticket(user_id: str) -> str:
        ticket = str(uuid.uuid4())
        try:
            redis_conn = django_redis.get_redis_connection('default')
            redis_conn.set(f'sse_ticket:{ticket}', user_id, ex=61)
        except Exception as e:
            logger.error(f'redis connection fault: {e}')

        return ticket

    @staticmethod
    def broadcast_to_user(to: str, notification: Notification):
        serializer = NotificationSerializer(notification)

        try:
            redis_conn = django_redis.get_redis_connection('default')
            payload = json.dumps(dict(serializer.data))
            channel_name = f'user_channel_{to}'

            if (
                0 == redis_conn.publish(channel_name, payload)
                and notification.type != notification.Type.ALERT
            ):
                redis_conn.lpush(channel_name, payload)
                redis_conn.expire(channel_name, 60)  # 60 secs

        except Exception as e:
            logger.error(f'redis brodcast to {to} error: {e}')

    @staticmethod
    def send_idempotent_notification(
        target_type,
        target_object,
        target_key,
        user_id,
        title,
        body,
        payload,
        channel=Notification.Channel.WEB,
        type=Notification.Type.ALERT,
        status=Notification.Status.UNREAD,
    ) -> Notification | None:
        str_target_id = str(target_object.id)

        log, created = NotificationLog.objects.get_or_create(
            user_id=user_id,
            target_type=target_type,
            target_id=str_target_id,
            target_key=target_key,
        )

        if not created:
            return None

        notif = Notification(
            user_id=user_id,
            title=title,
            body=body,
            type=type,
            channel=channel,
            status=status,
            payload=payload,
        )

        notif.save()

        NotificationServices.broadcast_to_user(user_id, notif)
        return notif

    @staticmethod
    def __send_undelted_notification(user_id):
        notis = Notification.objects.filter(user_id=user_id, deleted_at=None).order_by('-id')[:20]

        for noti in notis:
            NotificationServices.broadcast_to_user(user_id, noti)

    @staticmethod
    def __send_upcoming_Event(user_id):
        now = timezone.now()
        seven_days_later = now + timedelta(days=7)

        user_upcoming_events = Event.objects.filter(
            event_teams__event_team_members__user_id=user_id,
            start_time__range=(now, seven_days_later),
        ).distinct()
        for event in user_upcoming_events:
            payload = EventSerializer(event).data
            body = f'{payload.get("name")} upcomping'

            NotificationServices.send_idempotent_notification(
                target_type='Event',
                target_object=event,
                target_key='upcoming_event',
                user_id=user_id,
                title='upcomping event',
                body=body,
                type=Notification.Type.STATUS_BAR,
                channel=Notification.Channel.WEB,
                status=Notification.Status.UNREAD,
                payload=json.dumps(dict(payload)),
            )
            # NotificationServices.broadcast_to_user(user_id, noti)

    @staticmethod
    def send_init_notifications(user_id):
        NotificationServices.__send_upcoming_Event(user_id)
        NotificationServices.__send_undelted_notification(user_id)
