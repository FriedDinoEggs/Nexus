# apps/matches/strategies.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .models import BaseMatch, MatchSet, PlayerMatch, TeamMatch


@dataclass
class MatchResult:
    """Unified match result format (always 7 fields)"""

    winner: str | None
    is_completed: bool
    score_summary: dict[str, Any]
    metadata: dict[str, Any] | None = None


class BaseScoringStrategy[T: BaseMatch](ABC):
    """Base class for scoring strategies"""

    def __init__(self, rule_config: dict[str, Any]):
        self.rule_config = rule_config

    @abstractmethod
    def evaluate(self, match_obj: T) -> MatchResult:
        pass

    def _determine_winner(self, score_a: int, score_b: int) -> str | None:
        """Determine the winner"""
        if score_a > score_b:
            return BaseMatch.WinnerChoices.TEAM_A
        elif score_b > score_a:
            return BaseMatch.WinnerChoices.TEAM_B
        elif score_a == score_b:
            # Return DRAW if scores are tied; validity is determined by upper-level logic
            return BaseMatch.WinnerChoices.DRAW
        return None

    def _get_side_names(self, match_obj: BaseMatch) -> tuple[str, str]:
        """Get team names for side A and B"""
        if isinstance(match_obj, TeamMatch):
            return (
                match_obj.team_a.team.name if match_obj.team_a else 'Unknown A',
                match_obj.team_b.team.name if match_obj.team_b else 'Unknown B',
            )
        elif hasattr(match_obj, 'team_match') and match_obj.team_match:
            tm = match_obj.team_match
            return (
                tm.team_a.team.name if tm.team_a else 'Unknown A',
                tm.team_b.team.name if tm.team_b else 'Unknown B',
            )
        return 'Unknown A', 'Unknown B'

    def _build_result(
        self,
        match_obj: BaseMatch,
        score_a: int,
        score_b: int,
        total_played: int,
        target_score: int,
        play_all: bool,
        winner: str | None = None,
        is_completed: bool = False,
    ) -> MatchResult:
        """Build unified result format"""
        if winner is None and is_completed:
            winner = self._determine_winner(score_a, score_b)

        if not is_completed:
            winner = None

        side_a_name, side_b_name = self._get_side_names(match_obj)

        return MatchResult(
            winner=winner,
            is_completed=is_completed,
            score_summary={
                'score_a': score_a,
                'score_b': score_b,
                'total_played': total_played,
                'target_score': target_score,
                'play_all': play_all,
                'side_a_name': side_a_name,
                'side_b_name': side_b_name,
            },
        )


class ScoringStrategyFactory:
    """Strategy Factory"""

    _strategies: dict[type[BaseMatch], type[BaseScoringStrategy]] = {}

    @classmethod
    def register(cls, match_type: type[BaseMatch]):
        def decorator(strategy_cls: type[BaseScoringStrategy]):
            cls._strategies[match_type] = strategy_cls
            return strategy_cls

        return decorator

    @classmethod
    def get_strategy(cls, match_obj: BaseMatch, rule_config: dict[str, Any]) -> BaseScoringStrategy:
        """Automatically select strategy based on rule_config"""
        strategy_class = cls._strategies.get(type(match_obj))
        if not strategy_class:
            raise ValueError(f'No strategy for {type(match_obj).__name__}')
        return strategy_class(rule_config)


# ========== PlayerMatch Strategy ==========
@ScoringStrategyFactory.register(PlayerMatch)
class PlayerScoringStrategy(BaseScoringStrategy[PlayerMatch]):
    """Player match strategy: Determine race-to-win or play-all sets based on configuration"""

    def evaluate(self, match_obj: PlayerMatch) -> MatchResult:
        winning_sets = self.rule_config.get('winning_sets', 3)
        play_all_sets = self.rule_config.get('play_all_sets', False)

        sets = MatchSet.objects.filter(player_match=match_obj).order_by('set_number')
        score_a, score_b, total_played = 0, 0, 0

        # Calculate current score
        for match_set in sets:
            total_played += 1
            if match_set.score_a > match_set.score_b:
                score_a += 1
            elif match_set.score_b > match_set.score_a:
                score_b += 1

        is_completed = False
        winner = None

        if not play_all_sets:
            if score_a >= winning_sets:
                is_completed = True
                winner = BaseMatch.WinnerChoices.TEAM_A
            elif score_b >= winning_sets:
                is_completed = True
                winner = BaseMatch.WinnerChoices.TEAM_B
            else:
                # Not reached target, consider as in progress
                is_completed = False
        else:
            # Play-all sets:
            # Assuming winning_sets = 3 means Best of 5, so total sets = 5 (3*2 - 1)
            expected_total_sets = (winning_sets * 2) - 1
            if total_played >= expected_total_sets:
                is_completed = True
                winner = self._determine_winner(score_a, score_b)
            else:
                is_completed = False

        return self._build_result(
            match_obj,
            score_a,
            score_b,
            total_played,
            winning_sets,
            play_all=play_all_sets,
            winner=winner,
            is_completed=is_completed,
        )


# ========== TeamMatch Strategy ==========
@ScoringStrategyFactory.register(TeamMatch)
class TeamScoringStrategy(BaseScoringStrategy[TeamMatch]):
    """Team match strategy: Determine race-to-win or play-all matches based on configuration"""

    def _sum_sub_matches(self, all_player_matches) -> tuple[int, int, int]:
        """Calculate total scores and finished match count"""
        score_a, score_b, total_finished = 0, 0, 0
        for player_match in all_player_matches:
            strategy = ScoringStrategyFactory.get_strategy(player_match, self.rule_config)
            result = strategy.evaluate(player_match)

            if result.is_completed:
                total_finished += 1
                if result.winner == BaseMatch.WinnerChoices.TEAM_A:
                    score_a += 1
                elif result.winner == BaseMatch.WinnerChoices.TEAM_B:
                    score_b += 1
        return score_a, score_b, total_finished

    def evaluate(self, match_obj: TeamMatch) -> MatchResult:
        team_winning_points = self.rule_config.get('team_winning_points', 3)
        play_all_matches = self.rule_config.get('play_all_matches', False)

        all_player_matches = match_obj.player_matches.all().order_by('number')
        total_scheduled = all_player_matches.count()

        score_a, score_b, total_finished = self._sum_sub_matches(all_player_matches)

        is_completed = False
        winner = None

        if not play_all_matches:
            if score_a >= team_winning_points:
                is_completed = True
                winner = BaseMatch.WinnerChoices.TEAM_A
            elif score_b >= team_winning_points:
                is_completed = True
                winner = BaseMatch.WinnerChoices.TEAM_B
            elif total_finished == total_scheduled:
                is_completed = True
                winner = self._determine_winner(score_a, score_b)
        else:
            if total_finished >= total_scheduled and total_scheduled > 0:
                is_completed = True
                winner = self._determine_winner(score_a, score_b)

        return self._build_result(
            match_obj,
            score_a,
            score_b,
            total_finished,
            team_winning_points,
            play_all=play_all_matches,
            winner=winner,
            is_completed=is_completed,
        )
