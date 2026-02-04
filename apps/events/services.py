from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count

from apps.teams.models import Team

from .models import (
    Event,
    EventMatchConfiguration,
    EventMatchTemplate,
    EventMatchTemplateItem,
    EventTeam,
    EventTeamMember,
    LunchOption,
    RegistrationLunchOrder,
)

User = get_user_model()


class EventService:
    @staticmethod
    def find_matching_template(items_data: list[dict]) -> EventMatchTemplate | None:
        """
        Finds an existing template that matches exactly the given items_data.
        Matching criteria:
        1. Same number of items.
        2. Each item must match number, format, and requirement.
        """
        count = len(items_data)
        candidates = EventMatchTemplate.objects.annotate(num_items=Count('items')).filter(
            num_items=count
        )

        sorted_input = sorted(items_data, key=lambda x: x['number'])

        for tmpl in candidates:
            tmpl_items = list(tmpl.items.all().order_by('number'))

            match = True
            for inp, db_item in zip(sorted_input, tmpl_items, strict=True):
                if (
                    inp['number'] != db_item.number
                    or inp.get('format', 'S') != db_item.format
                    or inp.get('requirement', '') != db_item.requirement
                ):
                    match = False
                    break
            if match:
                return tmpl
        return None

    @staticmethod
    @transaction.atomic
    def get_or_create_match_template_from_items(
        *, name_prefix: str, items_data: list[dict], creator: User | None = None
    ) -> EventMatchTemplate:
        """
        Finds a matching template or creates a new one.
        """
        existing = EventService.find_matching_template(items_data)
        if existing:
            return existing

        new_name = f'{name_prefix} Template'
        return EventService.create_match_template(
            name=new_name, items_data=items_data, creator=creator
        )

    @staticmethod
    @transaction.atomic
    def create_match_template(
        *, name: str, items_data: list[dict], creator: User | None = None
    ) -> EventMatchTemplate:
        """Create a match template with its items."""
        template = EventMatchTemplate.objects.create(name=name, creator=creator)
        items = [
            EventMatchTemplateItem(
                template=template,
                number=item['number'],
                format=item.get('format', EventMatchTemplateItem.MatchFormatChoice.SINGLE),
                requirement=item.get('requirement', ''),
            )
            for item in items_data
        ]
        EventMatchTemplateItem.objects.bulk_create(items)
        return template

    @staticmethod
    @transaction.atomic
    def update_match_template(
        *,
        template: EventMatchTemplate,
        name: str | None = None,
        items_data: list[dict] | None = None,
    ) -> EventMatchTemplate:
        """Update a match template and its items."""
        if name is not None:
            template.name = name
            template.save()

        if items_data is not None:
            template.items.all().delete()
            items = [
                EventMatchTemplateItem(
                    template=template,
                    number=item['number'],
                    format=item.get('format', EventMatchTemplateItem.MatchFormatChoice.SINGLE),
                    requirement=item.get('requirement', ''),
                )
                for item in items_data
            ]
            EventMatchTemplateItem.objects.bulk_create(items)

        return template

    @staticmethod
    @transaction.atomic
    def set_event_config(
        event: Event, template: EventMatchTemplate | None = None, rule_config: dict | None = None
    ) -> EventMatchConfiguration:
        if rule_config is None:
            rule_config = {}

        defaults = {
            'template': template,
            'winning_sets': rule_config.get('winning_sets', 3),
            'set_winning_points': rule_config.get('set_winning_points', 11),
            'use_deuce': rule_config.get('use_deuce', True),
            'team_winning_points': rule_config.get('team_winning_points', 3),
            'play_all_sets': rule_config.get('play_all_sets', False),
            'play_all_matches': rule_config.get('play_all_matches', False),
            'count_points_by_sets': rule_config.get('count_points_by_sets', False),
        }

        config, created = EventMatchConfiguration.objects.update_or_create(
            event=event, defaults=defaults
        )
        return config

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

        new_template = EventMatchTemplate.objects.create(name=template_name, creator=creator)
        items = [
            EventMatchTemplateItem(
                template=new_template,
                number=item['number'],
                format=item.get('format', EventMatchTemplateItem.MatchFormatChoice.SINGLE),
                requirement=item.get('requirement', ''),
            )
            for item in format_data
        ]
        EventMatchTemplateItem.objects.bulk_create(items)

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
            EventService._validate_item(input_item, template_item)

    @staticmethod
    def _validate_item(input_item: dict, template_item: EventMatchTemplateItem):
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
    @transaction.atomic
    def create_event(
        *,
        name: str,
        event_type: str,
        start_time=None,
        end_time=None,
        location=None,
        lunch_options: list[str] = None,
    ) -> Event:
        """
        Creates a new event with the specified type.
            name: The name of the event.
            event_type: One of Event.TypeChoices (e.g., 'TN', 'LG', 'FR').
            start_time: (Optional) Datetime object.
            end_time: (Optional) Datetime object.
            location: (Optional) Location instance.
            lunch_options: (Optional) List of lunch option names.
        """

        event = Event(
            name=name, type=event_type, start_time=start_time, end_time=end_time, location=location
        )

        event.full_clean()
        event.save()

        if lunch_options:
            options = [LunchOption(event=event, name=opt_name) for opt_name in lunch_options]
            LunchOption.objects.bulk_create(options)

        return event

    @staticmethod
    @transaction.atomic
    def order_member_lunches(
        *, member: EventTeamMember, lunch_orders: list[dict] = None
    ) -> list[RegistrationLunchOrder]:
        """
        Creates lunch orders for a specific event team member.
        lunch_orders example: [
            {'option_id': 1, 'quantity': 2, 'note': 'No spicy'},
            {'option_id': 2, 'quantity': 1, 'note': 'Extra water'}
        ]
        """
        created_orders = []

        if lunch_orders:
            try:
                event = member.event_team.event
            except (AttributeError, ObjectDoesNotExist):
                raise ValidationError('This member is not associated with a valid event.') from None

            valid_option_ids = set(event.lunch_options.values_list('id', flat=True))

            for order in lunch_orders:
                opt_id = order.get('option_id')
                if opt_id not in valid_option_ids:
                    raise ValidationError(f'Invalid lunch option ID {opt_id} for this event.')

                created_orders.append(
                    RegistrationLunchOrder(
                        member=member,
                        option_id=opt_id,
                        quantity=order.get('quantity', 1),
                        note=order.get('note', ''),
                    )
                )

            if created_orders:
                RegistrationLunchOrder.objects.bulk_create(created_orders)

        return created_orders

    @staticmethod
    @transaction.atomic
    def register_team(
        *, event: Event, team: Team, status=EventTeam.StatusChoices.APPROVED
    ) -> EventTeam:
        """
        Registers a team to an event.
        """
        try:
            event_team = EventTeam(
                event=event, team=team, status=status, coach=team.coach, leader=team.leader
            )
            event_team.full_clean()
            event_team.save()
            return event_team
        except IntegrityError:
            raise ValidationError(
                f'Team {team.name} is already registered for this event.'
            ) from None

    @staticmethod
    @transaction.atomic
    def add_team_member(
        *, event_team: EventTeam, user, is_player=True, is_coach=False, is_staff=False
    ) -> EventTeamMember:
        """
        Adds a user to a specific EventTeam roster.
        Uses select_for_update on the user to prevent concurrent registrations
        across different teams in the same event.
        """
        try:
            # Lock the user record to prevent race conditions during cross-team validation
            _ = User.objects.select_for_update().get(pk=user.pk)

            member = EventTeamMember(
                event_team=event_team,
                user=user,
                is_player=is_player,
                is_coach=is_coach,
                is_staff=is_staff,
            )

            member.full_clean()
            member.save()
            return member
        except IntegrityError:
            raise ValidationError("User is already in this team's roster.") from None

    @staticmethod
    @transaction.atomic
    def del_team_member(*, event_team: EventTeam, user: User):
        event_team.event_team_members.filter(user=user).delete()

    @staticmethod
    def get_user_event_teams(*, user_id) -> EventTeam:
        queryset = (
            EventTeam.objects.filter(event_team_members__user_id=user_id)
            .select_related('event', 'team', 'coach', 'leader')
            .distinct()
        )

        return queryset

    @staticmethod
    def is_privileged(user: User) -> bool:
        is_privileged = user.groups.filter(name__in=['SuperAdmin', 'EventManager']).exists()

        return is_privileged
