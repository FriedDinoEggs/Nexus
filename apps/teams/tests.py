import logging
from contextlib import contextmanager

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.teams.models import Team

User = get_user_model()


@contextmanager
def suppress_django_request_warnings():
    logger = logging.getLogger('django.request')
    old_level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(old_level)


class TeamAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='SuperAdmin')
        self.manager_group, _ = Group.objects.get_or_create(name='EventManager')
        self.member_group, _ = Group.objects.get_or_create(name='Member')

        self.admin = User.objects.create_user(
            email='teams-admin@test.com',
            password='AdminPass123!@#',
            full_name='Teams Admin',
        )
        self.admin.groups.set([self.admin_group])

        self.manager = User.objects.create_user(
            email='teams-manager@test.com',
            password='ManagerPass123!@#',
            full_name='Teams Manager',
        )
        self.manager.groups.set([self.manager_group])

        self.member = User.objects.create_user(
            email='teams-member@test.com',
            password='MemberPass123!@#',
            full_name='Teams Member',
        )
        self.member.groups.set([self.member_group])

        self.list_url = reverse('v1:teams_app:teams-list')

    def test_manager_can_create_team(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.list_url,
            {'name': 'Manager Team'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        team = Team.objects.get(pk=response.data['id'])
        self.assertEqual(team.name, 'Manager Team')
        self.assertEqual(team.creator, self.manager)

    def test_member_cannot_create_team(self):
        self.client.force_authenticate(user=self.member)

        with suppress_django_request_warnings():
            response = self.client.post(
                self.list_url,
                {'name': 'Forbidden Team'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_update_team_name(self):
        team = Team.objects.create(name='Original Name', creator=self.manager)
        self.client.force_authenticate(user=self.manager)

        response = self.client.patch(
            reverse('v1:teams_app:teams-detail', kwargs={'id': team.pk}),
            {'name': 'Updated Name'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team.refresh_from_db()
        self.assertEqual(team.name, 'Updated Name')

    def test_admin_can_soft_delete_team(self):
        team = Team.objects.create(name='Delete Me', creator=self.manager)
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(
            reverse('v1:teams_app:teams-detail', kwargs={'id': team.pk}),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        team.refresh_from_db()
        self.assertIsNotNone(team.deleted_at)

    def test_join_team_sends_notifications(self):
        from apps.notification.models import Notification
        from apps.teams.services import TeamService

        team = Team.objects.create(name='Test Team', creator=self.manager, leader=self.manager)
        new_member = User.objects.create_user(
            email='new-joiner@test.com',
            password='Pass123!@#',
            full_name='New Joiner',
        )

        TeamService.join_team(team=team, user=new_member)

        # Joined user notification
        user_noti = Notification.objects.filter(user=new_member, title='【隊伍邀請通知】').first()
        self.assertIsNotNone(user_noti)
        self.assertIn('Test Team', user_noti.body)

        # Leader notification
        leader_noti = Notification.objects.filter(
            user=self.manager, title='【隊伍成員變動】'
        ).first()
        self.assertIsNotNone(leader_noti)
        self.assertIn('New Joiner', leader_noti.body)

    def test_leave_team_sends_notifications(self):
        from apps.notification.models import Notification
        from apps.teams.services import TeamService

        team = Team.objects.create(name='Test Team', creator=self.manager, leader=self.manager)
        member = User.objects.create_user(
            email='leaver@test.com',
            password='Pass123!@#',
            full_name='Leaver User',
        )
        TeamService.join_team(team=team, user=member)
        Notification.objects.all().delete()

        TeamService.leave_team(team=team, user=member)

        # Leaving user notification
        user_noti = Notification.objects.filter(user=member, title='【退出隊伍通知】').first()
        self.assertIsNotNone(user_noti)

        # Leader notification
        leader_noti = Notification.objects.filter(
            user=self.manager, title='【隊伍成員變動】'
        ).first()
        self.assertIsNotNone(leader_noti)

    def test_transfer_leadership_sends_notifications(self):
        from apps.notification.models import Notification
        from apps.teams.services import TeamService

        team = Team.objects.create(name='Test Team', creator=self.manager, leader=self.manager)
        new_leader = User.objects.create_user(
            email='new-leader@test.com',
            password='Pass123!@#',
            full_name='New Leader',
        )
        TeamService.join_team(team=team, user=new_leader)
        Notification.objects.all().delete()

        TeamService.transfer_leadership(team=team, new_leader=new_leader)

        noti = Notification.objects.filter(user=new_leader, title='【隊長身分轉讓】').first()
        self.assertIsNotNone(noti)
        self.assertIn('Test Team', noti.body)

    def test_disband_team_and_kick_member_sends_system_alert(self):
        from apps.notification.models import Notification
        from apps.teams.services import TeamService

        team = TeamService.create_team(user=self.manager, name='Alert Team', leader=self.manager)
        m1 = User.objects.create_user(
            email='kicked@test.com', password='Pass123!@#', full_name='Kicked User'
        )
        TeamService.join_team(team=team, user=m1)
        Notification.objects.all().delete()

        # Test kick member -> SYSTEM_ALERT
        TeamService.kick_member(team=team, target_user=m1)
        kick_noti = Notification.objects.filter(user=m1, type=Notification.Type.ALERT).first()
        self.assertIsNotNone(kick_noti)
        self.assertEqual(kick_noti.title, '【隊伍成員變動告警】')

        # Test disband team -> SYSTEM_ALERT
        TeamService.disband_team(team=team)
        disband_noti = Notification.objects.filter(
            user=self.manager, type=Notification.Type.ALERT
        ).first()
        self.assertIsNotNone(disband_noti)
        self.assertEqual(disband_noti.title, '【隊伍解散告警】')
