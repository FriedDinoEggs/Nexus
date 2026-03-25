import logging
from contextlib import contextmanager

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import Event, EventMatchConfiguration, EventMatchTemplate, EventTeam
from apps.matches.models import TeamMatch
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


class TeamMatchAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='manager@example.com', password='password', full_name='Manager User'
        )
        self.member = User.objects.create_user(
            email='member@example.com', password='password', full_name='Member User'
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
        self.team_c_base = Team.objects.create(name='Team C', creator=self.user)
        self.team_c = EventTeam.objects.create(event=self.event, team=self.team_c_base)

        self.other_event = Event.objects.create(name='Other Event')
        self.other_team_base = Team.objects.create(name='Other Team', creator=self.user)
        self.other_event_team = EventTeam.objects.create(
            event=self.other_event, team=self.other_team_base
        )

        # Setup Match Template and Config
        self.template = EventMatchTemplate.objects.create(
            name='Standard Template', creator=self.user
        )
        self.config = EventMatchConfiguration.objects.create(
            event=self.event,
            template=self.template,
            team_winning_points=3,
        )

        self.list_url = reverse('v1:matches_app:team-matches-list')
        self.nested_list_url = reverse(
            'v1:events_app:team-matches-nested-list', kwargs={'event_team_id': self.team_a.id}
        )

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

    def test_nested_list_filters_by_event_team(self):
        included = TeamMatch.objects.create(team_a=self.team_a, team_b=self.team_b, number=1)
        TeamMatch.objects.create(team_a=self.team_b, team_b=self.team_c, number=2)

        response = self.client.get(self.nested_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], included.id)

    def test_member_cannot_create_team_match(self):
        self.client.force_authenticate(user=self.member)
        with suppress_django_request_warnings():
            response = self.client.post(
                self.list_url,
                {
                    'team_a': self.team_a.id,
                    'team_b': self.team_b.id,
                    'number': 5,
                    'player_matches': [],
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_update_team_match_number(self):
        team_match = TeamMatch.objects.create(team_a=self.team_a, team_b=self.team_b, number=1)

        response = self.client.patch(
            reverse('v1:matches_app:team-matches-detail', kwargs={'pk': team_match.pk}),
            {'number': 9},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team_match.refresh_from_db()
        self.assertEqual(team_match.number, 9)

    def test_manager_can_delete_team_match(self):
        team_match = TeamMatch.objects.create(team_a=self.team_a, team_b=self.team_b, number=1)

        response = self.client.delete(
            reverse('v1:matches_app:team-matches-detail', kwargs={'pk': team_match.pk}),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        team_match.refresh_from_db()
        self.assertIsNotNone(team_match.deleted_at)

    def test_create_team_match_rejects_cross_event_matchup(self):
        with suppress_django_request_warnings():
            response = self.client.post(
                self.list_url,
                {
                    'team_a': self.team_a.id,
                    'team_b': self.other_event_team.id,
                    'number': 6,
                    'player_matches': [],
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_team_match_rejects_same_team_matchup(self):
        with suppress_django_request_warnings():
            response = self.client.post(
                self.list_url,
                {
                    'team_a': self.team_a.id,
                    'team_b': self.team_a.id,
                    'number': 7,
                    'player_matches': [],
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
