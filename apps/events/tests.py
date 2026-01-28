from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import EventMatchTemplate

User = get_user_model()


class MatchTemplateAPITests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin@example.com', password='password', full_name='Admin User'
        )
        self.event_manager_user = User.objects.create_user(
            email='manager@example.com', password='password', full_name='Manager User'
        )
        self.regular_user = User.objects.create_user(
            email='user@example.com', password='password', full_name='Regular User'
        )

        self.admin_group, _ = Group.objects.get_or_create(name='SuperAdmin')
        self.manager_group, _ = Group.objects.get_or_create(name='EventManager')

        self.admin_user.groups.add(self.admin_group)
        self.event_manager_user.groups.add(self.manager_group)

        self.template_url = reverse('v1:events_app:match-templates-list')

    def test_create_template_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'name': 'Admin Template',
            'items': [
                {'number': 1, 'format': 'S', 'requirement': "Men's Singles"},
                {'number': 2, 'format': 'D', 'requirement': "Men's Doubles"},
            ],
        }
        response = self.client.post(self.template_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EventMatchTemplate.objects.count(), 1)
        self.assertEqual(EventMatchTemplate.objects.first().items.count(), 2)

    def test_create_template_as_manager(self):
        self.client.force_authenticate(user=self.event_manager_user)
        data = {
            'name': 'Manager Template',
            'items': [{'number': 1, 'format': 'S', 'requirement': "Women's Singles"}],
        }
        response = self.client.post(self.template_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_template_as_regular_user_forbidden(self):
        self.client.force_authenticate(user=self.regular_user)
        data = {'name': 'Regular Template', 'items': []}
        response = self.client.post(self.template_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_templates_authenticated(self):
        initial_count = EventMatchTemplate.objects.count()
        EventMatchTemplate.objects.create(name='Public Template', creator=self.admin_user)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.template_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle pagination
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertEqual(response.data['count'], initial_count + 1)
        else:
            self.assertEqual(len(response.data), initial_count + 1)
