from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import Event, EventMatchConfiguration, EventMatchTemplate, EventTeam
from apps.matches.models import TeamMatch
from apps.teams.models import Team

User = get_user_model()


class TeamMatchAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com', password='password', full_name='Test User'
        )
        self.manager_group, _ = Group.objects.get_or_create(name='EventManager')
        self.user.groups.add(self.manager_group)
        self.client.force_authenticate(user=self.user)

        # Setup basic event and teams
        self.event = Event.objects.create(name='Test Event')
        self.team_a_base = Team.objects.create(name='Team A', creator=self.user)
        self.team_b_base = Team.objects.create(name='Team B', creator=self.user)

        self.team_a = EventTeam.objects.create(event=self.event, team=self.team_a_base)
        self.team_b = EventTeam.objects.create(event=self.event, team=self.team_b_base)

        # Setup Match Template and Config
        self.template = EventMatchTemplate.objects.create(
            name='Standard Template', creator=self.user
        )
        self.config = EventMatchConfiguration.objects.create(
            event=self.event, template=self.template, rule_config={'team_winning_points': 3}
        )

        self.list_url = reverse('v1:matches_app:team-matches-list')

    def test_list_team_matches(self):
        TeamMatch.objects.create(team_a=self.team_a, team_b=self.team_b, number=1)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check pagination
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertEqual(response.data['count'], 1)
        else:
            self.assertEqual(len(response.data), 1)

    def test_create_team_match(self):
        data = {
            'team_a': self.team_a.id,
            'team_b': self.team_b.id,
            'number': 2,
            'player_matches': [
                {'number': 1, 'side_a': [{'player': self.user.id, 'position': 1}], 'side_b': []}
            ],
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TeamMatch.objects.filter(number=2).count(), 1)
