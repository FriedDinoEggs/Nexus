from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.events.models import Event, EventMatchConfiguration, EventTeam

from .models import (
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
    def create_match_template(
        *, name: str, items_data: list[dict], creator: User | None = None
    ) -> MatchTemplate:
        """Create a match template with its items."""
        template = MatchTemplate.objects.create(name=name, creator=creator)
        items = [
            MatchTemplateItem(
                template=template,
                number=item['number'],
                format=item.get('format', MatchTemplateItem.MatchFormatChoice.SINGLE),
                requirement=item.get('requirement', ''),
            )
            for item in items_data
        ]
        MatchTemplateItem.objects.bulk_create(items)
        return template

    @staticmethod
    @transaction.atomic
    def update_match_template(
        *, template: MatchTemplate, name: str | None = None, items_data: list[dict] | None = None
    ) -> MatchTemplate:
        """Update a match template and its items."""
        if name is not None:
            template.name = name
            template.save()

        if items_data is not None:
            template.items.all().delete()
            items = [
                MatchTemplateItem(
                    template=template,
                    number=item['number'],
                    format=item.get('format', MatchTemplateItem.MatchFormatChoice.SINGLE),
                    requirement=item.get('requirement', ''),
                )
                for item in items_data
            ]
            MatchTemplateItem.objects.bulk_create(items)

        return template

    @staticmethod
    @transaction.atomic
    def set_event_config(
        event: Event, template: MatchTemplate, rule_config: dict = None
    ) -> EventMatchConfiguration:
        if rule_config is None:
            rule_config = {}

        config, created = EventMatchConfiguration.objects.update_or_create(
            event=event, defaults={'template': template, 'rule_config': rule_config}
        )
        return config

    @staticmethod
    @transaction.atomic
    def create_team_match_full(
        *, team_a: EventTeam, team_b: EventTeam, match_number: int, player_matches_data: list[dict]
    ) -> TeamMatch:
        """Create a TeamMatch and its player lineups in one go."""
        # 1. Initialize the TeamMatch and its player matches (empty slots) via template
        team_match = MatchService.initialize_team_match(team_a, team_b, match_number)

        # 2. Get the created player matches to assign participants
        # We use a map for quick lookup by match number
        pm_map = {pm.number: pm for pm in team_match.player_matches.all()}

        # 3. Assign participants
        for pm_data in player_matches_data:
            pm_num = pm_data.get('number')
            pm = pm_map.get(pm_num)
            if not pm:
                continue

            for part_data in pm_data.get('participants', []):
                MatchService.assign_player_to_match(
                    player_match=pm,
                    player=part_data.get('player'),
                    position=part_data.get('position', 1),
                    guest_name=part_data.get('player_name_backup'),
                    side=part_data.get('side'),
                )

        return team_match

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

        # Distributed Lock using Redis to prevent race conditions on match_number
        lock_key = f'lock:team_match_create:{event.id}:{match_number}'

        if hasattr(cache, 'lock'):
            lock = cache.lock(lock_key, timeout=10, blocking_timeout=5, sleep=0.1)

            if lock.acquire():
                try:
                    if TeamMatch.objects.filter(team_a__event=event, number=match_number).exists():
                        raise ValidationError(
                            f'Match number {match_number} '
                            f'is already assigned for event {event.name}.'
                        )

                    team_match = TeamMatch.objects.create(
                        team_a=team_a, team_b=team_b, number=match_number
                    )
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

                    transaction.on_commit(lambda: lock.release())

                except Exception as e:
                    lock.release()
                    raise e

            else:
                raise ValidationError(
                    'System is busy processing this match number. Please try again.'
                )

        else:
            # FIX: CI環境 LocMemCache 沒有lock= = 先這樣頂一下
            if TeamMatch.objects.filter(team_a__event=event, number=match_number).exists():
                raise ValidationError(
                    f'Match number {match_number} is already assigned for event {event.name}.'
                )

            team_match = TeamMatch.objects.create(team_a=team_a, team_b=team_b, number=match_number)

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
    def assign_player_to_match(
        player_match: PlayerMatch,
        player: User | None = None,
        position: int = 1,
        guest_name: str | None = None,
        side: str | None = None,
    ):
        """Assign player or guest to a specific match position."""
        team_match = player_match.team_match

        if not team_match.team_a or not team_match.team_b:
            raise ValueError('Can not assign players to match with missing team reference.')

        if player:
            membership = (
                player.eventteammember_set.filter(event_team__event=team_match.team_a.event)
                .select_related('event_team')
                .first()
            )

            if not membership:
                raise ValueError(f'Player {player} is not registered in this event.')

            player_event_team = membership.event_team
            if player_event_team == team_match.team_a:
                side = PlayerMatchParticipant.SideChoices.SIDE_A
            elif player_event_team == team_match.team_b:
                side = PlayerMatchParticipant.SideChoices.SIDE_B
            else:
                raise ValueError(f'Player {player} does not belong to either competing team.')
        else:
            if not guest_name:
                raise ValueError('Either player or guest_name must be provided.')
            if not side:
                raise ValueError('Side must be provided for guest players.')

        participant, _ = PlayerMatchParticipant.objects.update_or_create(
            player_match=player_match,
            # If guest, we lookup/update by name within this match
            # This is simplified; usually you'd want a unique identifier for guest
            side=side,
            position=position,
            defaults={'player': player, 'player_name_backup': guest_name or ''},
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
