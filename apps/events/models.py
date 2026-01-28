from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
                name='%(app_label)s_%(class)s_check_start_time_before_end_time',
                violation_error_message='The event end time must be later than the start time.',
            ),
        ]

    def __str__(self):
        return self.name


class EventTeam(TimeStampedModel):
    class StatusChoices(models.TextChoices):
        PENDING = 'PD', 'Pending'
        APPROVED = 'AP', 'Approved'
        REJECT = 'RJ', 'Rejected'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='event_teams')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='event_teams')

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
                name='%(app_label)s_%(class)s_unique_event_team',
                violation_error_message='The combination of Event and Team must be unique',
            ),
        ]

    def __str__(self):
        return f'{self.team.name} in {self.event.name}'


class EventTeamMember(TimeStampedModel):
    event_team = models.ForeignKey(
        EventTeam, on_delete=models.CASCADE, related_name='event_team_members'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_player = models.BooleanField(default=False, blank=True)
    is_coach = models.BooleanField(default=False, blank=True)
    is_staff = models.BooleanField(default=False, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['event_team', 'user'],
                name='%(app_label)s_%(class)s_unique_eventteam_user',
                violation_error_message='The combination of EventTeam and User must be unique',
            )
        ]

    def __str__(self):
        return f'{self.user.full_name} in ({self.event_team})'

    def clean(self):
        if not hasattr(self, 'event_team') or self.event_team is None:
            return
        if not hasattr(self, 'user') or self.user is None:
            return

        event = self.event_team.event
        if (
            EventTeamMember.objects.filter(event_team__event=event, user=self.user)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError('User is already registered in another team for this event.')


class LunchOption(TimeStampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='lunch_options')
    name = models.CharField(max_length=64)
    price = models.PositiveIntegerField(default=80)

    def __str__(self):
        return f'{self.name} ({self.event.name})'


class RegistrationLunchOrder(TimeStampedModel):
    member = models.ForeignKey(
        EventTeamMember, on_delete=models.CASCADE, related_name='lunch_orders'
    )
    option = models.ForeignKey(LunchOption, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    note = models.TextField(default='', blank=True)

    def __str__(self):
        return f'{self.member.user.full_name}: {self.quantity} x {self.option.name}'


class PlayerMatchConfiguration(models.Model):
    class MatchFormatChoice(models.TextChoices):
        SINGLE = 'S', 'Single'
        DOUBLE = 'D', 'Double'

    format = models.CharField(
        max_length=1,
        choices=MatchFormatChoice.choices,
        default=MatchFormatChoice.SINGLE,
        verbose_name='match format',
    )
    requirement = models.CharField(
        max_length=32,
        default='',
        blank=True,
        verbose_name='Match requirement',
        help_text=(
            'Specify the age, gender, or category for this match'
            ' (e.g., "30+ Men\'s Singles", "120+ Mixed Doubles").'
        ),
    )

    class Meta:
        abstract = True


class EventMatchTemplate(TimeStampedModel):
    name = models.CharField(max_length=128, verbose_name='Template Name')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class EventMatchTemplateItem(PlayerMatchConfiguration, TimeStampedModel):
    template = models.ForeignKey(EventMatchTemplate, on_delete=models.CASCADE, related_name='items')
    number = models.IntegerField(default=0)

    class Meta:
        ordering = ['number']
        constraints = [
            UniqueConstraint(
                fields=['template', 'number'],
                name='%(app_label)s_%(class)s_unique_template_item_number',
                violation_error_message='Match number must be unique within a template.',
            )
        ]

    def __str__(self):
        return f'{self.template.name} - Match {self.number}'


def get_default_rule_config():
    return {
        'winning_sets': 3,  # Number of sets to win a PlayerMatch
        'set_winning_points': 11,  # Points needed to win a single set
        'use_deuce': True,  # Whether to use deuce rule (must win by 2 points)
        'team_winning_points': 3,  # Number of points (matches) to win a TeamMatch
        'play_all_sets': False,  # Must play all sets, overrides winning_sets setting
        'play_all_matches': False,  # Must play all matches, overrides team_winning_points setting
        'count_points_by_sets': False,  # Whether to count set scores (e.g. 4ㄚ:2) or win/loss (1:0)
    }


class EventMatchConfiguration(TimeStampedModel):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='match_config')

    template = models.ForeignKey(
        EventMatchTemplate, on_delete=models.PROTECT, related_name='event_configs'
    )

    rule_config = models.JSONField(
        default=get_default_rule_config,
        blank=True,
        help_text='Configuration for scoring rules (e.g. winning_sets, etc.)',
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Config for {self.event.name} using {self.template.name}'
