from rest_framework import serializers

from apps.notification.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'type',
            'body',
            'payload',
            'channel',
            'status',
            'user_id',
            'created_at',
            'updated_at',
        ]
