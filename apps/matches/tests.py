from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.events.models import (
    Event,
    EventMatchConfiguration,
    EventMatchTemplate,
    EventMatchTemplateItem,
    EventTeam,
    EventTeamMember,
)
from apps.matches.models import (
    BaseMatch,
    PlayerMatchParticipant,
)
from apps.matches.serializers import TeamMatchSerializer
from apps.matches.services import MatchService
from apps.teams.models import Team

User = get_user_model()


class MatchScoringTests(TestCase):
    def setUp(self):
        # Create basic event structure
        self.user = User.objects.create_user(
            email='test@example.com', full_name='Test User', password='password'
        )
        self.event = Event.objects.create(name='Test Event')

        t_a = Team.objects.create(name='Team A', creator=self.user)
        t_b = Team.objects.create(name='Team B', creator=self.user)

        self.team_a = EventTeam.objects.create(event=self.event, team=t_a)
        self.team_b = EventTeam.objects.create(event=self.event, team=t_b)

        # Setup Template
        self.template = EventMatchTemplate.objects.create(
            name='Standard 5 Matches', creator=self.user
        )
        for i in range(1, 6):
            EventMatchTemplateItem.objects.create(template=self.template, number=i)

        self.config = EventMatchConfiguration.objects.create(
            event=self.event,
            template=self.template,
            winning_sets=3,
            team_winning_points=3,
            play_all_sets=False,
            play_all_matches=False,
        )

        # Initialize a Team Match
        self.team_match = MatchService.initialize_team_match(self.team_a, self.team_b, 1)
        self.player_matches = list(self.team_match.player_matches.all().order_by('number'))

    def test_player_match_race_to_win(self):
        """Test PlayerMatch completes when winning_sets is reached (Race mode)"""
        pm = self.player_matches[0]

        # A wins 1st set
        MatchService.record_set_score(pm, 1, 11, 5)
        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.IN_PROGRESS)

        # A wins 2nd set
        MatchService.record_set_score(pm, 2, 11, 5)
        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.IN_PROGRESS)

        # A wins 3rd set -> Should be Complete (3-0)
        MatchService.record_set_score(pm, 3, 11, 5)
        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.COMPLETED)
        self.assertEqual(pm.winner, BaseMatch.WinnerChoices.TEAM_A)

    def test_player_match_play_all(self):
        """Test PlayerMatch waits for all sets (Play All mode)"""
        # Update config to play_all_sets = True
        self.config.play_all_sets = True
        self.config.save()

        pm = self.player_matches[0]

        # A wins 3 sets (would be win in race mode)
        MatchService.record_set_score(pm, 1, 11, 0)
        MatchService.record_set_score(pm, 2, 11, 0)
        MatchService.record_set_score(pm, 3, 11, 0)

        pm.refresh_from_db()
        # Should still be IN_PROGRESS because winning_sets=3 implies Best of 5 (Total 5 sets)
        self.assertEqual(pm.status, BaseMatch.StatusChoices.IN_PROGRESS)

        # Play remaining 2 sets
        MatchService.record_set_score(pm, 4, 11, 0)
        MatchService.record_set_score(pm, 5, 11, 0)

        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.COMPLETED)
        self.assertEqual(pm.winner, BaseMatch.WinnerChoices.TEAM_A)

    def test_team_match_race_to_win(self):
        """Test TeamMatch completes when team_winning_points is reached"""
        # A wins Match 1
        self._win_player_match(self.player_matches[0], 'A')
        self.team_match.refresh_from_db()
        self.assertEqual(self.team_match.status, BaseMatch.StatusChoices.IN_PROGRESS)

        # A wins Match 2
        self._win_player_match(self.player_matches[1], 'A')

        # A wins Match 3 -> Team Match should be Complete (3-0)
        self._win_player_match(self.player_matches[2], 'A')

        self.team_match.refresh_from_db()
        self.assertEqual(self.team_match.status, BaseMatch.StatusChoices.COMPLETED)
        self.assertEqual(self.team_match.winner, BaseMatch.WinnerChoices.TEAM_A)

    def test_team_match_play_all(self):
        """Test TeamMatch waits for all matches (Play All mode)"""
        self.config.play_all_matches = True
        self.config.save()

        # A wins 3 matches (would be win in race mode)
        for i in range(3):
            self._win_player_match(self.player_matches[i], 'A')

        self.team_match.refresh_from_db()
        self.assertEqual(self.team_match.status, BaseMatch.StatusChoices.IN_PROGRESS)

        # Finish remaining matches
        self._win_player_match(self.player_matches[3], 'B')
        self._win_player_match(self.player_matches[4], 'B')

        self.team_match.refresh_from_db()
        self.assertEqual(self.team_match.status, BaseMatch.StatusChoices.COMPLETED)
        self.assertEqual(self.team_match.winner, BaseMatch.WinnerChoices.TEAM_A)  # 3-2 for A

    def test_match_status_regression(self):
        """Test status rolls back from COMPLETED to IN_PROGRESS if score changes"""
        pm = self.player_matches[0]

        # Make A win 3-0
        MatchService.record_set_score(pm, 1, 11, 0)
        MatchService.record_set_score(pm, 2, 11, 0)
        MatchService.record_set_score(pm, 3, 11, 0)

        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.COMPLETED)

        # Change 3rd set to be incomplete logic?
        # Actually, let's just make B win the 3rd set. Now score is 2-1. Target is 3.
        # So it should go back to IN_PROGRESS.
        MatchService.record_set_score(pm, 3, 0, 11)

        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.IN_PROGRESS)
        self.assertEqual(pm.winner, '')

    def test_team_match_status_regression(self):
        """Test TeamMatch status regression when a child match changes status"""
        # Win 3 matches for A
        for i in range(3):
            self._win_player_match(self.player_matches[i], 'A')

        self.team_match.refresh_from_db()
        self.assertEqual(self.team_match.status, BaseMatch.StatusChoices.COMPLETED)

        # Now revert the 3rd match to be IN_PROGRESS
        # Match 3 was won 3-0 by A. Let's change set 3 to B win -> 2-1 In Progress
        pm3 = self.player_matches[2]
        MatchService.record_set_score(pm3, 3, 0, 11)

        pm3.refresh_from_db()
        self.assertEqual(pm3.status, BaseMatch.StatusChoices.IN_PROGRESS)

        # Team Match should now be IN_PROGRESS (Only 2 wins for A)
        self.team_match.refresh_from_db()
        self.assertEqual(self.team_match.status, BaseMatch.StatusChoices.IN_PROGRESS)
        self.assertEqual(self.team_match.winner, '')

    def _win_player_match(self, player_match, winner_code):
        """Helper to quickly make a player match won by A or B"""
        score_a = 11 if winner_code == 'A' else 0
        score_b = 11 if winner_code == 'B' else 0

        # Win 3 sets
        for i in range(1, 4):
            MatchService.record_set_score(player_match, i, score_a, score_b)

    def test_team_match_count_by_sets(self):
        """
        Test TeamMatch score shows set totals when count_points_by_sets is True.
        Scenario:
        Match 1: A wins 3-2 (3 sets for A, 2 for B)
        Match 2: B wins 3-1 (1 set for A, 3 for B)
        Total should be 4:5
        """
        self.config.count_points_by_sets = True
        self.config.play_all_matches = True
        self.config.save()

        # Match 1: A wins 3-2 (A:3, B:2)
        pm1 = self.player_matches[0]
        MatchService.record_set_score(pm1, 1, 11, 5)  # A
        MatchService.record_set_score(pm1, 2, 5, 11)  # B
        MatchService.record_set_score(pm1, 3, 11, 5)  # A
        MatchService.record_set_score(pm1, 4, 5, 11)  # B
        MatchService.record_set_score(pm1, 5, 11, 5)  # A

        # Match 2: B wins 3-1 (A:1, B:3)
        pm2 = self.player_matches[1]
        MatchService.record_set_score(pm2, 1, 5, 11)  # B
        MatchService.record_set_score(pm2, 2, 11, 5)  # A
        MatchService.record_set_score(pm2, 3, 5, 11)  # B
        MatchService.record_set_score(pm2, 4, 5, 11)  # B

        # Complete pm3, pm4, pm5 as draws (0-0 sets) if possible, but let's give them some scores.
        # pm3: 0-0 (for simplicity, but record_set_score needs winners usually for matches)
        # Match 3: B wins 3-0 (A:0, B:3)
        self._win_player_match(self.player_matches[2], 'B')
        # Match 4: A wins 3-0 (A:3, B:0)
        self._win_player_match(self.player_matches[3], 'A')
        # Match 5: B wins 3-0 (A:0, B:3)
        self._win_player_match(self.player_matches[4], 'B')

        # Totals:
        # A sets: 3 (pm1) + 1 (pm2) + 0 (pm3) + 3 (pm4) + 0 (pm5) = 7
        # B sets: 2 (pm1) + 3 (pm2) + 3 (pm3) + 0 (pm4) + 3 (pm5) = 11

        # Evaluation
        from apps.matches.rules import ScoringStrategyFactory

        strategy = ScoringStrategyFactory.get_strategy(self.team_match, self.config.rule_config)
        result = strategy.evaluate(self.team_match)

        self.assertTrue(result.is_completed)
        self.assertEqual(result.score_summary['score_a'], 7)
        self.assertEqual(result.score_summary['score_b'], 11)
        self.assertEqual(result.winner, BaseMatch.WinnerChoices.TEAM_B)

    def test_player_match_deuce(self):
        """Test deuce logic: must win by 2 points when use_deuce is True"""
        self.config.use_deuce = True
        self.config.set_winning_points = 11
        self.config.winning_sets = 1
        self.config.save()

        pm = self.player_matches[0]

        # Score 11:10 -> Not completed yet
        MatchService.record_set_score(pm, 1, 11, 10)
        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.IN_PROGRESS)

        # Score 12:10 -> Completed
        MatchService.record_set_score(pm, 1, 12, 10)
        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.COMPLETED)
        self.assertEqual(pm.winner, BaseMatch.WinnerChoices.TEAM_A)

    def test_player_match_no_deuce(self):
        """Test no-deuce logic: ends exactly at target score"""
        self.config.use_deuce = False
        self.config.set_winning_points = 11
        self.config.winning_sets = 1
        self.config.save()

        pm = self.player_matches[0]

        # Score 11:10 -> Completed immediately
        MatchService.record_set_score(pm, 1, 11, 10)
        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.COMPLETED)
        self.assertEqual(pm.winner, BaseMatch.WinnerChoices.TEAM_A)


class MatchServiceAndSerializerTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email='matches@example.com',
            full_name='Matches User',
            password='password',
        )
        self.event = Event.objects.create(name='Service Event')
        self.other_event = Event.objects.create(name='Other Service Event')

        team_a_base = Team.objects.create(name='Service Team A', creator=self.manager)
        team_b_base = Team.objects.create(name='Service Team B', creator=self.manager)
        team_c_base = Team.objects.create(name='Service Team C', creator=self.manager)

        self.team_a = EventTeam.objects.create(event=self.event, team=team_a_base)
        self.team_b = EventTeam.objects.create(event=self.event, team=team_b_base)
        self.other_event_team = EventTeam.objects.create(event=self.other_event, team=team_c_base)

        self.template = EventMatchTemplate.objects.create(
            name='Service Template',
            creator=self.manager,
        )
        EventMatchTemplateItem.objects.create(template=self.template, number=1, format='S')
        EventMatchTemplateItem.objects.create(template=self.template, number=2, format='D')

        self.config = EventMatchConfiguration.objects.create(
            event=self.event,
            template=self.template,
            winning_sets=3,
            team_winning_points=2,
        )

        self.team_match = MatchService.initialize_team_match(self.team_a, self.team_b, 1)
        self.player_match = self.team_match.player_matches.get(number=1)

        self.player_a = User.objects.create_user(
            email='player-a@example.com',
            full_name='Player A',
            password='password',
        )
        self.player_b = User.objects.create_user(
            email='player-b@example.com',
            full_name='Player B',
            password='password',
        )
        self.player_outsider = User.objects.create_user(
            email='outsider@example.com',
            full_name='Outsider',
            password='password',
        )

        EventTeamMember.objects.create(event_team=self.team_a, user=self.player_a, is_player=True)
        EventTeamMember.objects.create(event_team=self.team_b, user=self.player_b, is_player=True)
        EventTeamMember.objects.create(
            event_team=self.other_event_team,
            user=self.player_outsider,
            is_player=True,
        )

    def test_initialize_team_match_rejects_cross_event_teams(self):
        with self.assertRaisesMessage(ValueError, 'Both teams must belong to the same event.'):
            MatchService.initialize_team_match(self.team_a, self.other_event_team, 2)

    def test_initialize_team_match_requires_event_match_config(self):
        event_without_config = Event.objects.create(name='No Config Event')
        team_x = EventTeam.objects.create(
            event=event_without_config,
            team=Team.objects.create(name='No Config A', creator=self.manager),
        )
        team_y = EventTeam.objects.create(
            event=event_without_config,
            team=Team.objects.create(name='No Config B', creator=self.manager),
        )

        with self.assertRaisesMessage(ValueError, 'No match configuration found for event'):
            MatchService.initialize_team_match(team_x, team_y, 1)

    def test_initialize_team_match_rejects_duplicate_match_number(self):
        with self.assertRaises(ValidationError):
            MatchService.initialize_team_match(self.team_a, self.team_b, 1)

    def test_assign_player_to_match_sets_side_from_event_team_membership(self):
        participant = MatchService.assign_player_to_match(
            player_match=self.player_match,
            player=self.player_a,
            position=1,
        )

        self.assertEqual(participant.side, PlayerMatchParticipant.SideChoices.SIDE_A)
        self.assertEqual(participant.player, self.player_a)

    def test_assign_player_to_match_rejects_player_not_registered_in_event(self):
        stranger = User.objects.create_user(
            email='stranger@example.com',
            full_name='Stranger',
            password='password',
        )

        with self.assertRaisesMessage(ValueError, 'is not registered in this event'):
            MatchService.assign_player_to_match(
                player_match=self.player_match,
                player=stranger,
                position=1,
            )

    def test_assign_player_to_match_rejects_player_from_other_event(self):
        with self.assertRaisesMessage(ValueError, 'is not registered in this event'):
            MatchService.assign_player_to_match(
                player_match=self.player_match,
                player=self.player_outsider,
                position=1,
            )

    def test_assign_player_to_match_requires_guest_name_for_guest(self):
        with self.assertRaisesMessage(ValueError, 'Either player or guest_name must be provided.'):
            MatchService.assign_player_to_match(
                player_match=self.player_match,
                side='A',
                position=1,
            )

    def test_assign_player_to_match_requires_side_for_guest(self):
        with self.assertRaisesMessage(ValueError, 'Side must be provided for guest players.'):
            MatchService.assign_player_to_match(
                player_match=self.player_match,
                guest_name='Guest Player',
                position=1,
            )

    @patch('apps.matches.serializers.MatchService.create_team_match_full')
    def test_team_match_serializer_maps_side_a_and_side_b_participants(
        self, mock_create_team_match
    ):
        serializer = TeamMatchSerializer(
            data={
                'team_a': self.team_a.id,
                'team_b': self.team_b.id,
                'number': 3,
                'player_matches': [
                    {
                        'number': 1,
                        'side_a': [{'player': self.player_a.id, 'position': 1}],
                        'side_b': [{'player': self.player_b.id, 'position': 2}],
                    }
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        mock_create_team_match.assert_called_once_with(
            team_a=self.team_a,
            team_b=self.team_b,
            match_number=3,
            player_matches_data=[
                {
                    'number': 1,
                    'participants': [
                        {'player': self.player_a.id, 'position': 1, 'side': 'A'},
                        {'player': self.player_b.id, 'position': 2, 'side': 'B'},
                    ],
                }
            ],
        )

    @patch('apps.matches.serializers.MatchService.create_team_match_full')
    def test_team_match_serializer_converts_service_errors_to_validation_errors(
        self, mock_create_team_match
    ):
        mock_create_team_match.side_effect = ValueError('invalid matchup')

        serializer = TeamMatchSerializer(
            data={
                'team_a': self.team_a.id,
                'team_b': self.team_b.id,
                'number': 4,
                'player_matches': [],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaisesMessage(DRFValidationError, 'invalid matchup'):
            serializer.save()
