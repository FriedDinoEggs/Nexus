from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.notification.models import Notification
from apps.notification.services.services import NotificationServices

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
    @transaction.atomic
    def join_team(team: Team, user: User, note: str = '') -> TeamMember:
        """
        Adds a user to the team and notifies the user and team leaders.
        """
        from django.db import IntegrityError

        try:
            member = TeamMember.objects.create(team=team, user=user, note=note)
        except IntegrityError:
            raise ValidationError(f'User {user} is already a member of team {team}.') from None

        # Notify the added user
        NotificationServices.send_notification(
            user_id=user.id,
            title='【隊伍邀請通知】',
            body=f'您已被加入隊伍「{team.name}」。',
            payload={'team_id': team.id, 'team_name': team.name},
            type=Notification.Type.SYSTEM_INFO,
        )

        # Notify leader and coach if different from joined user
        user_display = user.full_name or user.username
        recipients = set()
        if team.leader and team.leader != user:
            recipients.add(team.leader.id)
        if team.coach and team.coach != user:
            recipients.add(team.coach.id)

        for target_user_id in recipients:
            NotificationServices.send_notification(
                user_id=target_user_id,
                title='【隊伍成員變動】',
                body=f'成員 {user_display} 已加入隊伍「{team.name}」。',
                payload={'team_id': team.id, 'user_id': user.id},
                type=Notification.Type.SYSTEM_INFO,
            )

        return member

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

        # Notify the user leaving
        NotificationServices.send_notification(
            user_id=user.id,
            title='【退出隊伍通知】',
            body=f'您已退出隊伍「{team.name}」。',
            payload={'team_id': team.id, 'team_name': team.name},
            type=Notification.Type.SYSTEM_INFO,
        )

        # Notify leader & coach if different
        user_display = user.full_name or user.username
        recipients = set()
        if team.leader and team.leader != user:
            recipients.add(team.leader.id)
        if team.coach and team.coach != user:
            recipients.add(team.coach.id)

        for target_user_id in recipients:
            NotificationServices.send_notification(
                user_id=target_user_id,
                title='【隊伍成員變動】',
                body=f'成員 {user_display} 已離開隊伍「{team.name}」。',
                payload={'team_id': team.id, 'user_id': user.id},
                type=Notification.Type.SYSTEM_INFO,
            )

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
    @transaction.atomic
    def transfer_leadership(team: Team, new_leader: User) -> Team:
        """
        Transfers leadership to another member and notifies the new leader.
        """
        if not TeamMember.objects.filter(team=team, user=new_leader).exists():
            raise ValidationError(f'User {new_leader} is not a member of this team.')

        team.leader = new_leader
        team.save()

        NotificationServices.send_notification(
            user_id=new_leader.id,
            title='【隊長身分轉讓】',
            body=f'您已成為隊伍「{team.name}」的新任隊長。',
            payload={'team_id': team.id, 'team_name': team.name},
            type=Notification.Type.SYSTEM_INFO,
        )

        return team

    @staticmethod
    @transaction.atomic
    def disband_team(team: Team) -> None:
        """
        Disbands a team and sends a SYSTEM_ALERT (SA) notification to all team members.
        """
        members = list(team.members.all())
        team_name = team.name
        team_id = team.id

        team.delete()

        for member in members:
            NotificationServices.send_notification(
                user_id=member.id,
                title='【隊伍解散告警】',
                body=f'您所在的隊伍「{team_name}」已被解散。',
                payload={'team_id': team_id, 'team_name': team_name},
                type=Notification.Type.ALERT,
            )

    @staticmethod
    @transaction.atomic
    def kick_member(team: Team, target_user: User) -> None:
        """
        Forcibly removes a member from a team and sends a SYSTEM_ALERT (SA) notification.
        """
        try:
            membership = TeamMember.objects.get(team=team, user=target_user)
        except TeamMember.DoesNotExist:
            raise ValidationError(f'User {target_user} is not a member of team {team}.') from None

        membership.delete()

        NotificationServices.send_notification(
            user_id=target_user.id,
            title='【隊伍成員變動告警】',
            body=f'您已被移出隊伍「{team.name}」。',
            payload={'team_id': team.id, 'team_name': team.name},
            type=Notification.Type.ALERT,
        )
