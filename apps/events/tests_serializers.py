from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, APITestCase

from apps.events.models import Event, EventTeam, EventTeamMember, LunchOption
from apps.events.serializers import (
    EventSerializer,
    EventTeamMemberSerializer,
    EventTeamSerializer,
)
from apps.teams.models import Team

User = get_user_model()


class TestEventTeamMemberSerializer(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='testuser@example.com', password='password', full_name='Test User'
        )
        self.team1 = Team.objects.create(name='Team 1', creator=self.user)
        self.team2 = Team.objects.create(name='Team 2', creator=self.user)
        self.event = Event.objects.create(name='Test Event', type='LG')
        self.event_team1 = EventTeam.objects.create(event=self.event, team=self.team1)
        self.event_team2 = EventTeam.objects.create(event=self.event, team=self.team2)

        self.factory = APIRequestFactory()
        self.request = self.factory.get('/')
        self.request.user = self.user

    def test_validate_prevent_multiple_registrations(self):
        # Create first registration
        EventTeamMember.objects.create(event_team=self.event_team1, user=self.user)

        # Try to register for another team in same event
        data = {'event_team': self.event_team2.id}
        serializer = EventTeamMemberSerializer(data=data, context={'request': self.request})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(serializers.ValidationError) as cm:
            serializer.save()
        self.assertIn(
            'User is already registered in another team for this event.', str(cm.exception)
        )

    def test_validate_allow_update_same_instance(self):
        # Create registration
        member = EventTeamMember.objects.create(
            event_team=self.event_team1, user=self.user, is_player=True
        )

        # Update registration (same instance)
        data = {'event_team': self.event_team1.id, 'is_player': False}
        serializer = EventTeamMemberSerializer(
            instance=member, data=data, context={'request': self.request}, partial=True
        )

        # This should be valid now!
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_works_as_expected(self):
        data = {'event_team': self.event_team1.id, 'is_player': True}
        serializer = EventTeamMemberSerializer(data=data, context={'request': self.request})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        member = serializer.save()
        self.assertEqual(member.user, self.user)
        self.assertEqual(member.event_team, self.event_team1)


class TestEventSerializer(APITestCase):
    def test_create_event_with_lunch_options(self):
        data = {
            'name': 'New Tournament',
            'type': 'TN',
            'lunch_options': [
                {'name': 'Standard', 'price': 80},
                {'name': 'Vegetarian', 'price': 100},
            ],
        }
        serializer = EventSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        event = serializer.save()

        self.assertEqual(event.name, 'New Tournament')
        self.assertEqual(event.type, 'TN')
        self.assertEqual(LunchOption.objects.filter(event=event).count(), 2)
        self.assertTrue(LunchOption.objects.filter(event=event, name='Standard').exists())

    def test_update_event_with_lunch_options(self):
        event = Event.objects.create(name='Old Event', type='LG')
        LunchOption.objects.create(event=event, name='Old Option')

        data = {
            'name': 'Updated Event',
            'lunch_options': [
                {'name': 'New Option 1', 'price': 90},
                {'name': 'New Option 2', 'price': 110},
            ],
        }
        serializer = EventSerializer(instance=event, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        event = serializer.save()

        self.assertEqual(event.name, 'Updated Event')
        # Check if lunch options were replaced
        self.assertEqual(LunchOption.objects.filter(event=event).count(), 2)

    def test_get_event_with_lunch_options(self):
        event = Event.objects.create(name='GET Event', type='LG')
        LunchOption.objects.create(event=event, name='Option 1', price=80)

        serializer = EventSerializer(instance=event)
        data = serializer.data

        self.assertEqual(len(data['lunch_options']), 1)
        self.assertEqual(data['lunch_options'][0]['name'], 'Option 1')
        # Check if 'event' field is present and correct
        self.assertEqual(data['lunch_options'][0]['event'], event.id)


class TestEventTeamSerializer(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='coach@example.com', password='password', full_name='Coach User'
        )
        self.event = Event.objects.create(name='League 2024', type='LG')
        self.team = Team.objects.create(name='The Tigers', creator=self.user, coach=self.user)

    def test_create_event_team(self):
        data = {
            'event': self.event.id,
            'team': self.team.id,
        }
        serializer = EventTeamSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        event_team = serializer.save()

        self.assertEqual(event_team.event, self.event)
        self.assertEqual(event_team.team, self.team)
        # Verify that coach was populated from the team by the service
        self.assertEqual(event_team.coach, self.user)
