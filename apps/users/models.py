from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

# Create your models here.

User = get_user_model()


class BlackListToken(models.Model):
    token = models.CharField(max_length=500, unique=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['expires_at'], name='exp_index'),
        ]

    def __str__(self):
        return f'Blacklisted: {self.token}'

    @classmethod
    def cleanup_expired(cls):
        cls.objects.filter(expires_at__lt=timezone.now()).delete()
