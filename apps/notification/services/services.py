import json
import logging
import uuid
from datetime import timedelta

import django_redis
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notification.models import Notification, NotificationLog
from apps.notification.serializers import NotificationSerializer

logger = logging.getLogger(__name__)


class NotificationServices:
    @staticmethod
    def gen_ticket(user_id: str) -> str:
        ticket = str(uuid.uuid4())
        try:
            redis_conn = django_redis.get_redis_connection('default')
            if redis_conn.set(f'sse_ticket:{ticket}', user_id, ex=61):
                return ticket

        except Exception as e:
            logger.error(f'redis connection fault: {e}')

        return ''

    @staticmethod
    def broadcast_to_user(to: str, notification: Notification):
        serializer = NotificationSerializer(notification)

        try:
            redis_conn = django_redis.get_redis_connection('default')
            payload = dict(serializer.data)
            if 'payload' in payload:
                payload['payload'] = json.dumps(payload['payload'])
            stream_name = f'user_notification_stream:{to}'

            redis_conn.xadd(stream_name, payload, id='*', maxlen=50, approximate=True)

        except Exception as e:
            logger.error(f'redis brodcast to {to} error: {e}')

    @staticmethod
    def send_notification(
        user_id,
        title,
        body,
        payload: dict,
        channel=Notification.Channel.WEB,
        type=Notification.Type.ALERT,
        status=Notification.Status.UNREAD,
        idempotent=False,
        target_type='',
        target_object=None,
        target_key='',
    ) -> Notification | None:
        with transaction.atomic():
            if idempotent:
                if not target_object or not hasattr(target_object, 'id'):
                    return None

                str_target_id = str(target_object.id)

                try:
                    with transaction.atomic():
                        log, created = NotificationLog.objects.get_or_create(
                            user_id=user_id,
                            target_type=target_type,
                            target_id=str_target_id,
                            target_key=target_key,
                        )
                except IntegrityError:
                    created = False

                if not created:
                    return None
            try:
                notif = Notification.objects.create(
                    user_id=user_id,
                    title=title,
                    body=body,
                    type=type,
                    channel=channel,
                    status=status,
                    payload=payload,
                )

                transaction.on_commit(
                    lambda: NotificationServices.broadcast_to_user(user_id, notif)
                )

                return notif
            except Exception as e:
                raise e

    @staticmethod
    def __send_undelted_notification(user_id):
        notis = Notification.objects.filter(user_id=user_id, deleted_at=None).order_by('-id')[:20]

        for noti in notis:
            NotificationServices.broadcast_to_user(user_id, noti)

    @staticmethod
    def __send_upcoming_Event(user_id):
        from apps.events.models import Event
        from apps.events.serializers import EventSerializer

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
                title='upcoming event',
                body=body,
                type=Notification.Type.STATUS_BAR,
                channel=Notification.Channel.WEB,
                status=Notification.Status.UNREAD,
                payload=dict(payload),
            )

    @staticmethod
    def send_init_notifications(user_id):
        NotificationServices.__send_upcoming_Event(user_id)
        NotificationServices.__send_undelted_notification(user_id)
