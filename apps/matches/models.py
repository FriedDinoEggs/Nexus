from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint
from django.db.models.functions import Greatest, Least

from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.events.models import EventTeam, PlayerMatchConfiguration

# Create your models here.
User = get_user_model()


class BaseMatch(SoftDeleteModel):
    class StatusChoices(models.TextChoices):
        SCHEDULED = 'SC', 'Scheduled'
        IN_PROGRESS = 'IP', 'In Progress'
        COMPLETED = 'CP', 'Completed'
        CANCELLED = 'XX', 'Cancelled'

    class WinnerChoices(models.TextChoices):
        TEAM_A = 'A', 'Team_A'
        TEAM_B = 'B', 'Team_B'
        DRAW = 'D', 'Draw'

    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    number = models.IntegerField(default=0)

    status = models.CharField(
        max_length=2,
        choices=StatusChoices.choices,
        default=StatusChoices.SCHEDULED,
    )
    winner = models.CharField(
        max_length=1,
        choices=WinnerChoices.choices,
        blank=True,
    )

    class Meta(SoftDeleteModel.Meta):
        ordering = ['number']
        abstract = True


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
            # e04有地雷！！！
            # postgreSQL Lease Greatest: 回傳 non-null 的最小/最大值，若全都 null 回傳 null
            # SQLite Oracle MySQl : Lease Greatest 如果有任何 expression 是 null 回傳 null
            UniqueConstraint(
                Least('team_a', 'team_b'),
                Greatest('team_a', 'team_b'),
                name='%(app_label)s_%(class)s_unique_matchup',
                violation_error_message='This team matchup already exists in the system.',
            ),
        ]

    def __str__(self):
        return f'Team Match number: {self.number}'

    def clean(self):
        if self.team_a and self.team_b:
            if self.team_a.event != self.team_b.event:
                raise ValidationError('Both teams must belong to the same event.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def full_display_name(self) -> str:
        name_a = self.team_a.team.name if self.team_a else 'Unknown'
        name_b = self.team_b.team.name if self.team_b else 'Unknown'
        return f'{name_a} vs {name_b}'


class PlayerMatch(BaseMatch, PlayerMatchConfiguration):
    team_match = models.ForeignKey(
        TeamMatch, on_delete=models.CASCADE, related_name='player_matches'
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


def get_default_rule_config():
    return {
        'winning_sets': 3,  # Number of sets to win a PlayerMatch
        'set_winning_points': 11,  # Points needed to win a single set
        'use_deuce': True,  # Whether to use deuce rule (must win by 2 points)
        'team_winning_points': 3,  # Number of points (matches) to win a TeamMatch
        'play_all_sets': False,  # Must play all sets, overrides winning_sets setting
        'play_all_matches': False,  # Must play all matches, overrides team_winning_points setting
        'count_points_by_sets': False,  # Whether to count set scores (e.g. 3:2) or win/loss (1:0)
    }


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
    class SideChoices(models.TextChoices):
        SIDE_A = 'A', 'Team A'
        SIDE_B = 'B', 'Team B'

    player_match = models.ForeignKey(
        PlayerMatch, on_delete=models.CASCADE, related_name='participants'
    )
    player = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='match_participations'
    )
    player_name_backup = models.CharField(default='', max_length=128, blank=True)

    side = models.CharField(
        max_length=1,
        choices=SideChoices.choices,
        default=SideChoices.SIDE_A,
        verbose_name='Side',
    )
    position = models.IntegerField(default=1, verbose_name='Position')

    class Meta(TimeStampedModel.Meta):
        abstract = False
        ordering = ['side', 'position']
        constraints = [
            UniqueConstraint(
                fields=['player_match', 'player'],
                name='%(app_label)s_%(class)s_unique_participant',
                violation_error_message='This player already exists for this match',
            ),
            UniqueConstraint(
                fields=['player_match', 'side', 'position'],
                name='%(app_label)s_%(class)s_unique_side_position',
                violation_error_message='This position on this side is already occupied.',
            ),
            CheckConstraint(
                condition=Q(position__in=[1, 2]),
                name='%(app_label)s_%(class)s_check_position_1_or_2',
                violation_error_message='Position must be 1 or 2',
            ),
        ]

    def __str__(self):
        player_name = self.player.full_name if self.player else 'Unknown Player'
        return f'{player_name} playing in {self.player_match} (Pos: {self.position})'

    def save(self, *argc, **kwargs):
        if self.player and not self.player_name_backup:
            self.player_name_backup = self.player.full_name[:128]
        return super().save(*argc, **kwargs)
