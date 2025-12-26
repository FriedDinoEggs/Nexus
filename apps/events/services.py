from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
        Create an Event and, if provided, create associated LunchOption records for it.
        
        If `lunch_options` is provided, a LunchOption is created for each name in the list and linked to the created event.
        
        Parameters:
            lunch_options (list[str], optional): Names of lunch options to create and associate with the event.
        
        Returns:
            Event: The created Event instance.
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
        Create registration lunch orders for an EventTeamMember from provided order descriptions.
        
        Each entry in `lunch_orders` must reference a lunch option that belongs to the member's event. When valid orders are provided, corresponding RegistrationLunchOrder records are created in bulk.
        
        Parameters:
            lunch_orders (list[dict] | None): Optional list of order dictionaries. Each dictionary should contain:
                - 'option_id' (int): ID of a LunchOption belonging to the event.
                - 'quantity' (int, optional): Number of portions (defaults to 1).
                - 'note' (str, optional): Free-text note for the order (defaults to empty string).
        
        Returns:
            list[RegistrationLunchOrder]: The list of created RegistrationLunchOrder instances; empty if no orders were created.
        
        Raises:
            ValidationError: If any provided `option_id` does not belong to the member's event.
        """
        created_orders = []

        if lunch_orders:
            event = member.event_team.event
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
        Register a team for an event.
        
        Parameters:
            event (Event): Event to register the team for.
            team (Team): Team being registered.
            status (EventTeam.StatusChoices | str): Registration status to assign; defaults to EventTeam.StatusChoices.APPROVED.
        
        Returns:
            EventTeam: The created EventTeam registration record.
        
        Raises:
            ValidationError: If the team is already registered for the event or the created record fails validation.
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
        Add a user to an EventTeam roster.
        
        Acquires a row-level lock on the user to prevent concurrent cross-team registrations, validates the new roster membership, and saves it.
        
        Parameters:
            event_team (EventTeam): The team registration to add the user to.
            user (User): The user to add to the roster.
            is_player (bool): Whether the user is a player on the team.
            is_coach (bool): Whether the user is a coach on the team.
            is_staff (bool): Whether the user is staff for the team.
        
        Returns:
            EventTeamMember: The created EventTeamMember instance.
        
        Raises:
            ValidationError: If the membership is invalid (model validation) or the user is already in the team's roster.
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