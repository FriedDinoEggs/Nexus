from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel

User = get_user_model()


class Team(SoftDeleteModel):
    name = models.CharField(max_length=255)

    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_teams')
    leader = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='led_teams'
    )
    coach = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='coached_teams'
    )
    members = models.ManyToManyField(User, through='TeamMember', related_name='teams')

    class Meta:
        default_manager_name = SoftDeleteModel.Meta.default_manager_name
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class TeamMemberManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(team__deleted_at__isnull=True)


class TeamMember(TimeStampedModel):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    note = models.TextField(default='', blank=True)

    all_objects = models.Manager()
    objects = TeamMemberManager()

    class Meta:
        default_manager_name = 'objects'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['team', 'user'],
                name='unique_team_member',
            )
        ]

    def __str__(self):
        return f'{self.user.full_name} in {self.team.name}'
