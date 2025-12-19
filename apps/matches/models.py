from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint

from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.events.models import EventTeam

# Create your models here.
User = get_user_model()


class BaseMatch(SoftDeleteModel):
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    number = models.IntegerField(default=0)

    class Meta(SoftDeleteModel.Meta):
        ordering = ['number']

    def status(self):
        raise NotImplementedError(
            f'Method "status" must be implemented in subclass "{self.__class__.__name__}"!!!'
        )
        ...


class TeamMatch(BaseMatch):
    team_a = models.ForeignKey(
        EventTeam, on_delete=models.SET_NULL, null=True, related_name='team_matches_a'
    )
    team_b = models.ForeignKey(
        EventTeam, on_delete=models.SET_NULL, null=True, related_name='team_matches_b'
    )

    class Meta(BaseMatch.Meta):
        abstract = False
        constraints = [
            CheckConstraint(
                condition=~Q(team_a=F('team_b')),
                name='%(app_label)s_%(class)s_check_team_a_ne_team_b',
                violation_error_message='Team A and Team B must be different.',
            ),
            UniqueConstraint(
                fields=['number'],
                name='%(app_label)s_%(class)s_unique_number',
                violation_error_message='Team match number must be unique',
            ),
        ]

    def __str__(self):
        return f'Team Match number: {self.number}'

    @property
    def full_display_name(self) -> str:
        name_a = self.team_a.team.name if self.team_a else 'Unknown'
        name_b = self.team_b.team.name if self.team_b else 'Unknown'
        return f'{name_a} vs {name_b}'


class PlayerMatch(BaseMatch):
    class MatchFormatChoice(models.TextChoices):
        SINGLE = 'S', 'Single'
        DOUBLE = 'D', 'Double'

    team_match = models.ForeignKey(
        TeamMatch, on_delete=models.CASCADE, related_name='player_matches'
    )
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

    class Meta(BaseMatch.Meta):
        abstract = False
        constraints = [
            UniqueConstraint(
                fields=['team_match', 'number'],
                name='%(app_label)s_%(class)s_unique_match_order',
                violation_error_message='This match number is already assigned in this team match.',
            ),
        ]

    def __str__(self):
        return f'Player match order {self.number} ({self.requirement})'


class MatchSet(TimeStampedModel):
    player_match = models.ForeignKey(PlayerMatch, on_delete=models.CASCADE, related_name='sets')
    set_number = models.IntegerField(default=0, verbose_name='set number')
    score_a = models.IntegerField(default=0, verbose_name='team A score')
    score_b = models.IntegerField(default=0, verbose_name='team B score')

    class Meta(TimeStampedModel.Meta):
        abstract = False
        ordering = ['set_number']
        constraints = [
            UniqueConstraint(
                fields=['player_match', 'set_number'],
                name='%(app_label)s_%(class)s_unique_match_set_order',
                violation_error_message='This set number already exists for this match',
            )
        ]

    def __str__(self):
        return f'set number: {self.set_number}'


class PlayerMatchParticipant(TimeStampedModel):
    player_match = models.ForeignKey(
        PlayerMatch, on_delete=models.CASCADE, related_name='participants'
    )
    player = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='match_participations')
    player_name_backup = models.CharField(max_length=128, null=True, blank=True)

    position = models.IntegerField(default=1, verbose_name='Position')

    class Meta(TimeStampedModel.Meta):
        abstract=False
        ordering = ['position']
        constraints = [
            UniqueConstraint(
                fields=['player_match', 'player'],
                name='%(app_label)s_%(class)s_unique_participant',
                violation_error_message='This player already exists for this match',
            )
        ]

    def __str__(self):
        return f"{self.player.full_name} playing in {self.player_match} (Pos: {self.position})"
    
    def save(self, *argc, **kwargs):
        if self.player and not self.player_name_backup:
            self.player_name_backup = self.player.full_name[:128]
        return super().save(*argc, **kwargs)
