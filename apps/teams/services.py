from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Team, TeamMember

User = get_user_model()


class TeamService:
    @staticmethod
    @transaction.atomic
    def create_team(user: User, name: str, **kwargs) -> Team:
        """
        Creates a new team and automatic adds creator/coach/leader to team.
        """
        if not name:
            raise ValidationError('Team name cannot be empty.')

        leader = kwargs.get('leader', None)
        coach = kwargs.get('coach', None)

        kwargs.setdefault('creator', user)

        team = Team.objects.create(name=name, **kwargs)

        teamMember_list = [user, leader, coach]
        members = {m for m in teamMember_list if m}

        for member_user in members:
            TeamMember.objects.get_or_create(team=team, user=member_user, defaults={'note': ''})

        return team

    @staticmethod
    def join_team(team: Team, user: User, note: str = '') -> TeamMember:
        """
        Adds a user to the team.
        """
        if TeamMember.objects.filter(team=team, user=user).exists():
            raise ValidationError(f'User {user} is already a member of team {team}.')

        return TeamMember.objects.create(team=team, user=user, note=note)

    @staticmethod
    @transaction.atomic
    def leave_team(team: Team, user: User) -> None:
        """
        Removes a user from the team.
        Prevents leader from leaving without transferring leadership.
        """
        try:
            membership = TeamMember.objects.get(team=team, user=user)
        except TeamMember.DoesNotExist:
            raise ValidationError(f'User {user} is not a member of team {team}.') from None

        if team.leader == user:
            member_count = team.members.count()
            if member_count > 1:
                raise ValidationError(
                    'Leader cannot leave the team. Please transfer leadership first.'
                )
            else:
                team.delete()
                return

        membership.delete()

    @staticmethod
    def update_team(team: Team, **data) -> Team:
        """
        Updates basic team information.
        Filters out sensitive fields like 'creator' or 'leader' to prevent accidental overrides.
        """
        if 'creator' in data or 'leader' in data:
            raise ValidationError(
                'Cannot update creator or leader via update_team. Use specific methods.'
            )

        for field, value in data.items():
            if hasattr(team, field):
                setattr(team, field, value)

        team.save()
        return team

    @staticmethod
    def transfer_leadership(team: Team, new_leader: User) -> Team:
        """
        Transfers leadership to another member.
        """
        if not TeamMember.objects.filter(team=team, user=new_leader).exists():
            raise ValidationError(f'User {new_leader} is not a member of this team.')

        team.leader = new_leader
        team.save()

        return team
