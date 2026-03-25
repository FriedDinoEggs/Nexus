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
