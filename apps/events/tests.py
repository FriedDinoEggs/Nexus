import logging
from contextlib import contextmanager

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.teams.models import Team

from .models import Event, EventMatchTemplate, EventTeam, EventTeamMember

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
        with suppress_django_request_warnings():
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


class EventAndEventTeamAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='SuperAdmin')
        self.manager_group, _ = Group.objects.get_or_create(name='EventManager')
        self.member_group, _ = Group.objects.get_or_create(name='Member')

        self.admin = User.objects.create_user(
            email='events-admin@test.com',
            password='AdminPass123!@#',
            full_name='Events Admin',
        )
        self.admin.groups.set([self.admin_group])

        self.manager = User.objects.create_user(
            email='events-manager@test.com',
            password='ManagerPass123!@#',
            full_name='Events Manager',
        )
        self.manager.groups.set([self.manager_group])

        self.member = User.objects.create_user(
            email='events-member@test.com',
            password='MemberPass123!@#',
            full_name='Events Member',
        )
        self.member.groups.set([self.member_group])

        self.events_url = reverse('v1:events_app:events-list')
        self.event_teams_me_url = reverse('v1:events_app:event-teams-me')

    def test_event_calendar_query_filters_by_time_range(self):
        now = timezone.now()
        in_range = Event.objects.create(
            name='In Range',
            type=Event.TypeChoices.LEAGUE,
            start_time=now,
            end_time=now + timezone.timedelta(hours=2),
        )
        Event.objects.create(
            name='Out Of Range',
            type=Event.TypeChoices.LEAGUE,
            start_time=now + timezone.timedelta(days=5),
            end_time=now + timezone.timedelta(days=5, hours=2),
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get(
            self.events_url,
            {
                'calendar': 'true',
                'start': (now - timezone.timedelta(hours=1)).isoformat(),
                'end': (now + timezone.timedelta(hours=3)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], in_range.id)
        self.assertEqual(response.data[0]['title'], in_range.name)

    def test_manager_can_create_event_team_with_new_team_name(self):
        event = Event.objects.create(name='League 2026', type=Event.TypeChoices.LEAGUE)
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse('v1:events_app:event-teams-nested-list', kwargs={'event_id': event.id}),
            {'new_team_name': 'Fresh Team'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event_team = EventTeam.objects.get(pk=response.data['id'])
        self.assertEqual(event_team.event, event)
        self.assertEqual(event_team.team.name, 'Fresh Team')
        self.assertEqual(event_team.team.creator, self.manager)

    def test_member_cannot_create_event_team(self):
        event = Event.objects.create(name='Members League', type=Event.TypeChoices.LEAGUE)
        self.client.force_authenticate(user=self.member)

        with suppress_django_request_warnings():
            response = self.client.post(
                reverse('v1:events_app:event-teams-nested-list', kwargs={'event_id': event.id}),
                {'new_team_name': 'Should Fail'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_event_teams_me_returns_only_joined_teams(self):
        event = Event.objects.create(name='Joined Event', type=Event.TypeChoices.LEAGUE)
        joined_team = Team.objects.create(name='Joined Team', creator=self.manager)
        other_team = Team.objects.create(name='Other Team', creator=self.manager)

        joined_event_team = EventTeam.objects.create(event=event, team=joined_team)
        EventTeam.objects.create(event=event, team=other_team)

        EventTeamMember.objects.create(event_team=joined_event_team, user=self.member)

        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.event_teams_me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['team_name'], 'Joined Team')

    def test_event_update_sends_notification(self):
        from apps.notification.models import Notification

        event = Event.objects.create(name='Original Event', type=Event.TypeChoices.LEAGUE)
        team = Team.objects.create(name='Sample Team', creator=self.manager)
        event_team = EventTeam.objects.create(event=event, team=team)
        EventTeamMember.objects.create(event_team=event_team, user=self.member)

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            reverse('v1:events_app:events-detail', kwargs={'id': event.id}),
            {'start_time': timezone.now().isoformat()},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        noti = Notification.objects.filter(
            user=self.member, title='【緊急賽程異動】請注意地點與時間'
        ).first()
        self.assertIsNotNone(noti)
        self.assertIn('Original Event', noti.body)

    def test_event_team_status_update_sends_notification(self):
        from apps.notification.models import Notification

        event = Event.objects.create(name='Review Event', type=Event.TypeChoices.LEAGUE)
        team = Team.objects.create(name='Review Team', creator=self.manager, leader=self.manager)
        event_team = EventTeam.objects.create(
            event=event, team=team, leader=self.manager, status=EventTeam.StatusChoices.PENDING
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            reverse('v1:events_app:event-teams-detail', kwargs={'id': event_team.id}),
            {'status': EventTeam.StatusChoices.APPROVED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        noti = Notification.objects.filter(user=self.manager, title='【隊伍報名審核結果】').first()
        self.assertIsNotNone(noti)
        self.assertIn('通過審核', noti.body)

    def test_event_team_member_registration_and_waitlist_promotion_notifications(self):
        from apps.notification.models import Notification

        event = Event.objects.create(name='Waitlist Event', type=Event.TypeChoices.LEAGUE)
        team = Team.objects.create(name='WL Team', creator=self.manager)
        event_team = EventTeam.objects.create(event=event, team=team, max_member=1, max_waitlist=2)

        # 1. First member registers -> REGULAR
        self.client.force_authenticate(user=self.member)
        res1 = self.client.post(
            reverse(
                'v1:events_app:members-nested-list',
                kwargs={'event_team_id': event_team.id},
            ),
            {},
            format='json',
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        m1_noti = Notification.objects.filter(user=self.member, title='【報名成功通知】').first()
        self.assertIsNotNone(m1_noti)

        # 2. Second member registers -> WAITLIST
        other_user = User.objects.create_user(
            email='wl-user@test.com', password='Pass123!@#', full_name='WL User'
        )
        other_user.groups.add(self.member_group)
        self.client.force_authenticate(user=other_user)
        res2 = self.client.post(
            reverse(
                'v1:events_app:members-nested-list',
                kwargs={'event_team_id': event_team.id},
            ),
            {},
            format='json',
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        m2_noti = Notification.objects.filter(user=other_user, title='【報名候補通知】').first()
        self.assertIsNotNone(m2_noti)

        # 3. First member withdraws -> Second member gets promoted!
        self.client.force_authenticate(user=self.member)
        del_res = self.client.delete(
            reverse(
                'v1:events_app:members-nested-detail',
                kwargs={
                    'event_team_id': event_team.id,
                    'id': res1.data['id'],
                },
            )
        )
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)

        # Check promotion notification for other_user
        promo_noti = Notification.objects.filter(user=other_user, title='【備取遞補成功】').first()
        self.assertIsNotNone(promo_noti)

    def test_event_deletion_sends_system_alert(self):
        from apps.notification.models import Notification

        event = Event.objects.create(name='Cancelled Event', type=Event.TypeChoices.LEAGUE)
        team = Team.objects.create(name='Sample Team', creator=self.manager)
        event_team = EventTeam.objects.create(event=event, team=team)
        EventTeamMember.objects.create(event_team=event_team, user=self.member)
        Notification.objects.all().delete()

        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(
            reverse('v1:events_app:events-detail', kwargs={'id': event.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        noti = Notification.objects.filter(user=self.member, type=Notification.Type.ALERT).first()
        self.assertIsNotNone(noti)
        self.assertEqual(noti.title, '【緊急通知】賽事已被取消')

    def test_event_team_deletion_sends_system_alert(self):
        from apps.notification.models import Notification

        event = Event.objects.create(name='Event Alpha', type=Event.TypeChoices.LEAGUE)
        team = Team.objects.create(name='Team Alpha', creator=self.manager, leader=self.manager)
        event_team = EventTeam.objects.create(event=event, team=team, leader=self.manager)
        EventTeamMember.objects.create(event_team=event_team, user=self.member)
        Notification.objects.all().delete()

        self.client.force_authenticate(user=self.manager)
        response = self.client.delete(
            reverse('v1:events_app:event-teams-detail', kwargs={'id': event_team.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        noti_member = Notification.objects.filter(
            user=self.member, type=Notification.Type.ALERT
        ).first()
        self.assertIsNotNone(noti_member)
        self.assertEqual(noti_member.title, '【隊伍報名取消告警】')

        noti_leader = Notification.objects.filter(
            user=self.manager, type=Notification.Type.ALERT
        ).first()
        self.assertIsNotNone(noti_leader)
