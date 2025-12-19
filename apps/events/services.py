from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.teams.models import Team

from .models import Event, EventTeam, EventTeamMember

User = get_user_model()


class EventService:
    @staticmethod
    def create_event(
        *, name: str, event_type: str, start_time=None, end_time=None, location=None
    ) -> Event:
        """
        Creates a new event with the specified type.
            name: The name of the event.
            event_type: One of Event.TypeChoices (e.g., 'TN', 'LG', 'FR').
            start_time: (Optional) Datetime object.
            end_time: (Optional) Datetime object.
            location: (Optional) Location instance.
        """

        event = Event(
            name=name, type=event_type, start_time=start_time, end_time=end_time, location=location
        )

        event.full_clean()
        event.save()

        return event

    @staticmethod
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
    def add_team_member(
        *, event_team: EventTeam, user, is_player=True, is_coach=False, is_staff=False
    ) -> EventTeamMember:
        """
        Adds a user to a specific EventTeam roster.
        Uses select_for_update on the user to prevent concurrent registrations
        across different teams in the same event.
        """
        try:
            with transaction.atomic():
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
