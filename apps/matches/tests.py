from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.events.models import (
    Event,
    EventMatchConfiguration,
    EventMatchTemplate,
    EventMatchTemplateItem,
    EventTeam,
)
from apps.matches.models import (
    BaseMatch,
)
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
            rule_config={
                'winning_sets': 3,
                'team_winning_points': 3,
                'play_all_sets': False,
                'play_all_matches': False,
            },
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
        self.config.rule_config['play_all_sets'] = True
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
        self.config.rule_config['play_all_matches'] = True
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
        self.config.rule_config['count_points_by_sets'] = True
        self.config.rule_config['play_all_matches'] = True
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
        self.config.rule_config['use_deuce'] = True
        self.config.rule_config['set_winning_points'] = 11
        self.config.rule_config['winning_sets'] = 1
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
        self.config.rule_config['use_deuce'] = False
        self.config.rule_config['set_winning_points'] = 11
        self.config.rule_config['winning_sets'] = 1
        self.config.save()

        pm = self.player_matches[0]

        # Score 11:10 -> Completed immediately
        MatchService.record_set_score(pm, 1, 11, 10)
        pm.refresh_from_db()
        self.assertEqual(pm.status, BaseMatch.StatusChoices.COMPLETED)
        self.assertEqual(pm.winner, BaseMatch.WinnerChoices.TEAM_A)
