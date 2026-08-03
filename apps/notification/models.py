from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import UniqueConstraint

from apps.core.models import SoftDeleteModel, TimeStampedModel

User = get_user_model()


class Notification(SoftDeleteModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_notifications')

    title = models.CharField(max_length=32, default='', null=False, blank=True)
    body = models.CharField(max_length=32, default='', null=False, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Channel(models.TextChoices):
        SMS = 'SMS', 'SMS'
        WEB = 'WEB', 'WEB'

    channel = models.CharField(max_length=3, choices=Channel.choices, default=Channel.WEB)

    class Type(models.TextChoices):
        ALERT = 'SA', 'SYSTEM_ALERT'
        STATUS_BAR = 'SB', 'STATUS_BAR'

    type = models.CharField(max_length=2, choices=Type.choices, default=Type.STATUS_BAR)

    class Status(models.TextChoices):
        UNREAD = 'UR', 'unread'
        READ = 'R', 'read'
        DELETED = 'D', 'deleted'

    status = models.CharField(max_length=2, choices=Status.choices, default=Status.UNREAD)

    class Meta:
        ordering = ['-id']


class NotificationLog(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_notification_logs')

    target_type = models.CharField(max_length=32, default='', null=False, blank=True)
    target_id = models.CharField(max_length=36, default='', null=False, blank=True)
    target_key = models.CharField(max_length=32, default='', null=False, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['user', 'target_type', 'target_id', 'target_key'],
                name='%(app_label)s_%(class)s_unique_user_targetType_targetID',
                violation_error_message='The combination of user/target_type'
                'and target_id must be unique',
            ),
        ]
