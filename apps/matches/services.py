from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.events.models import Event, EventTeam

from .models import (
    EventMatchConfiguration,
    MatchSet,
    MatchTemplate,
    MatchTemplateItem,
    PlayerMatch,
    PlayerMatchParticipant,
    TeamMatch,
)
from .rules import ScoringStrategyFactory

User = get_user_model()


class MatchService:
    @staticmethod
    @transaction.atomic
    def initialize_team_match(team_a: EventTeam, team_b: EventTeam, match_number: int):
        """Initialize a team match and create scheduled matches based on Event's MatchTemplate"""
        if team_a.event != team_b.event:
            raise ValueError('Both teams must belong to the same event.')

        event = team_a.event
        try:
            config = event.match_config
            template = config.template
        except EventMatchConfiguration.DoesNotExist:
            raise ValueError(f'No match configuration found for event {event.name}') from None

        items_to_create = [
            {'number': item.number, 'format': item.format, 'requirement': item.requirement}
            for item in template.items.all()
        ]

        team_match = TeamMatch.objects.create(team_a=team_a, team_b=team_b, number=match_number)

        player_matches = [
            PlayerMatch(
                team_match=team_match,
                number=item['number'],
                format=item['format'],
                requirement=item['requirement'],
            )
            for item in items_to_create
        ]
        PlayerMatch.objects.bulk_create(player_matches)
        return team_match

    @staticmethod
    @transaction.atomic
    def configure_event_match_format(
        event: Event,
        format_data: list[dict],
        template_name: str | None = None,
        creator: User | None = None,
    ):
        """Configure or update event match format template"""
        if not template_name:
            template_name = f'{event.name} Format'

        new_template = MatchTemplate.objects.create(name=template_name, creator=creator)
        items = [
            MatchTemplateItem(
                template=new_template,
                number=item['number'],
                format=item.get('format', MatchTemplateItem.MatchFormatChoice.SINGLE),
                requirement=item.get('requirement', ''),
            )
            for item in format_data
        ]
        MatchTemplateItem.objects.bulk_create(items)

        EventMatchConfiguration.objects.update_or_create(
            event=event, defaults={'template': new_template}
        )
        return new_template

    @staticmethod
    def validate_match_format(event: Event, format_data: list[dict]) -> None:
        """Validate if input format matches the event's current template"""
        try:
            config = event.match_config
            template = config.template
        except EventMatchConfiguration.DoesNotExist:
            raise ValidationError('No match configuration set for this event.') from None

        template_items = list(template.items.all().order_by('number'))
        if len(format_data) != len(template_items):
            raise ValidationError(
                f'Number of matches mismatch: expected {len(template_items)}, '
                f'got {len(format_data)}.'
            )

        sorted_input = sorted(format_data, key=lambda x: x.get('number', 0))
        for input_item, template_item in zip(sorted_input, template_items, strict=True):
            MatchService._validate_item(input_item, template_item)

    @staticmethod
    def _validate_item(input_item: dict, template_item: MatchTemplateItem):
        """Internal validation for a single item format"""
        if input_item.get('number') != template_item.number:
            raise ValidationError(f'Match number mismatch at index {input_item.get("number")}.')

        if input_item.get('format') != template_item.format:
            raise ValidationError(
                f'Format mismatch for match {template_item.number}: '
                f'expected {template_item.get_format_display()}, '
                f'got {input_item.get("format")}.'
            )

        if input_item.get('requirement') != template_item.requirement:
            raise ValidationError(
                f'Requirement mismatch for match {template_item.number}: '
                f"expected '{template_item.requirement}', "
                f"got '{input_item.get('requirement')}'."
            )

    @staticmethod
    def assign_player_to_match(player_match: PlayerMatch, player: User, position: int = 1):
        """Assign player to a specific match position and validate team eligibility"""
        team_match = player_match.team_match

        if not team_match.team_a or not team_match.team_b:
            raise ValueError('Can not assign players to match with missing theam referenct.')

        membership = (
            player.eventteammember_set.filter(event_team__event=team_match.team_a.event)
            .select_related('event_team')
            .first()
        )

        if not membership:
            raise ValueError(f'Player {player} is not registered in this event.')

        player_event_team = membership.event_team
        if player_event_team not in [team_match.team_a, team_match.team_b]:
            raise ValueError(f'Player {player} does not belong to either competing team.')

        participant, _ = PlayerMatchParticipant.objects.update_or_create(
            player_match=player_match, player=player, defaults={'position': position}
        )
        return participant

    @staticmethod
    @transaction.atomic
    def record_set_score(player_match: PlayerMatch, set_number: int, score_a: int, score_b: int):
        """Record score for a set and check if match is completed"""
        MatchSet.objects.update_or_create(
            player_match=player_match,
            set_number=set_number,
            defaults={'score_a': score_a, 'score_b': score_b},
        )
        try:
            config = player_match.team_match.team_a.event.match_config.rule_config
        except (AttributeError, EventMatchConfiguration.DoesNotExist):
            config = {}

        MatchService._update_player_match_status(player_match, config)

    @staticmethod
    def _update_player_match_status(player_match: PlayerMatch, rule_config: dict):
        """Update PlayerMatch status and winner"""
        strategy = ScoringStrategyFactory.get_strategy(player_match, rule_config)
        result = strategy.evaluate(player_match)

        new_status = (
            PlayerMatch.StatusChoices.COMPLETED
            if result.is_completed
            else PlayerMatch.StatusChoices.IN_PROGRESS
        )

        new_winner = result.winner if result.winner else ''

        if player_match.status != new_status or player_match.winner != new_winner:
            player_match.status = new_status
            player_match.winner = new_winner
            player_match.save(update_fields=['status', 'winner'])

        MatchService._update_team_match_status(player_match.team_match, rule_config)

    @staticmethod
    def _update_team_match_status(team_match: TeamMatch, rule_config: dict):
        """Update TeamMatch status and winner"""
        strategy = ScoringStrategyFactory.get_strategy(team_match, rule_config)
        result = strategy.evaluate(team_match)

        new_status = (
            TeamMatch.StatusChoices.COMPLETED
            if result.is_completed
            else TeamMatch.StatusChoices.IN_PROGRESS
        )

        new_winner = result.winner if result.winner else ''

        if team_match.status != new_status or team_match.winner != new_winner:
            team_match.status = new_status
            team_match.winner = new_winner
            team_match.save(update_fields=['status', 'winner'])
