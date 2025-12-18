from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint

from apps.core.models import Location, SoftDeleteModel, TimeStampedModel
from apps.teams.models import Team

# Create your models here.

User = get_user_model()


class Event(SoftDeleteModel):
    class TypeChoices(models.TextChoices):
        TOURNAMENT = 'TN', 'Tournament'
        LEAGUE = 'LG', 'League'
        FRIENDLY = 'FR', 'Friendly'

    name = models.CharField(max_length=128, verbose_name='Event name')
    teams = models.ManyToManyField(Team, through='EventTeam', related_name='events')
    type = models.CharField(
        max_length=2,
        choices=TypeChoices.choices,
        default=TypeChoices.LEAGUE,
        verbose_name='Event Type',
    )
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='events'
    )
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_manager_name = SoftDeleteModel.Meta.default_manager_name
        ordering = ['-created_at']

        constraints = [
            CheckConstraint(
                condition=Q(start_time__isnull=True)
                | Q(end_time__isnull=True)
                | Q(start_time__lt=F('end_time')),
                name='check_start_time_before_end_time',
                violation_error_message='The event end time must be later than the start time.',
            ),
        ]

    def __str__(self):
        return self.name


class EventTeam(TimeStampedModel):
    class StatusChoices(models.TextChoices):
        PENDING = 'PD', 'Pending'
        APPROVED = 'AP', 'Approved'
        REJECT = 'RJ', 'Reject'

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    coach = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='coached_event_teams'
    )
    leader = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='led_event_teams'
    )

    status = models.CharField(
        max_length=2, choices=StatusChoices.choices, default=StatusChoices.APPROVED
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['event', 'team'],
                name='unique_event_team',
                violation_error_message='The combination of Event and Team must be unique',
            ),
        ]

    def __str__(self):
        return f'{self.team.name} in {self.event.name}'
