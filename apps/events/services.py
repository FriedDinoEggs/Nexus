from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, transaction

from apps.teams.models import Team

from .models import (
    Event,
    EventTeam,
    EventTeamMember,
    LunchOption,
    RegistrationLunchOrder,
)

User = get_user_model()


class EventService:
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
