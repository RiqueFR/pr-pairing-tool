import pytest

from pr_pairing import select_reviewers, KnowledgeMode, Developer, History


class TestSelectReviewers:
    def test_no_self_review(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Alice", can_review=True)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={}
        )
        
        assert "Alice" not in selected
        assert len(selected) == 1
        assert "Bob" in selected

    def test_select_correct_number(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Alice", can_review=True)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={}
        )
        
        assert len(selected) == 2

    def test_select_fewer_when_not_enough(self):
        candidates = [
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Alice", can_review=True)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=3,
            team_mode=False,
            current_assignments={}
        )
        
        assert len(selected) == 1

    def test_experts_only_filter(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=5),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=2),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=4),
        ]
        dev = Developer(name="Dana", can_review=True)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=3,
            team_mode=False,
            current_assignments={},
            knowledge_mode=KnowledgeMode.EXPERTS_ONLY
        )
        
        assert "Bob" not in selected
        assert "Alice" in selected
        assert "Charlie" in selected
        assert len(selected) == 2

    def test_mentorship_novice_gets_expert(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=5),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=2),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=4),
        ]
        dev = Developer(name="Dana", can_review=True, knowledge_level=1)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            knowledge_mode=KnowledgeMode.MENTORSHIP
        )
        
        assert "Bob" not in selected
        assert "Alice" in selected
        assert "Charlie" in selected

    def test_mentorship_senior_can_get_anyone(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=5),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=2),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=4),
        ]
        dev = Developer(name="Dana", can_review=True, knowledge_level=4)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            knowledge_mode=KnowledgeMode.MENTORSHIP
        )
        
        assert "Bob" in selected or "Alice" in selected or "Charlie" in selected

    def test_similar_levels_filters_by_one_level(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=5),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=1),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True, knowledge_level=2)
        history = History(pairs={}, last_run=None)

        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            knowledge_mode=KnowledgeMode.SIMILAR_LEVELS
        )

        assert "Charlie" in selected
        assert "Bob" in selected
        assert "Alice" not in selected

    def test_similar_levels_warns_when_no_similar_reviewers(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=5),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=5),
        ]
        dev = Developer(name="Dana", can_review=True, knowledge_level=1)
        history = History(pairs={}, last_run=None)

        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            knowledge_mode=KnowledgeMode.SIMILAR_LEVELS
        )

        assert len(selected) == 0
        assert any("within 1 knowledge level" in w for w in warnings)

    def test_similar_levels_allows_exact_level_match(self):
        candidates = [
            Developer(name="Alice", can_review=True, knowledge_level=3),
            Developer(name="Bob", can_review=True, knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True, knowledge_level=3)
        history = History(pairs={}, last_run=None)

        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            knowledge_mode=KnowledgeMode.SIMILAR_LEVELS
        )

        assert "Alice" in selected
        assert "Bob" in selected

    def test_similar_levels_edge_case_level_1(self):
        candidates = [
            Developer(name="Alice", can_review=True, knowledge_level=2),
            Developer(name="Bob", can_review=True, knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True, knowledge_level=1)
        history = History(pairs={}, last_run=None)

        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            knowledge_mode=KnowledgeMode.SIMILAR_LEVELS
        )

        assert "Alice" in selected
        assert "Bob" not in selected

    def test_team_mode_prioritizes_same_team(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Alice", can_review=True, team="frontend")
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=True,
            current_assignments={}
        )
        
        assert "Bob" in selected
        assert "Charlie" in selected or "Alice" not in selected

    def test_history_affects_selection(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True)
        history = History(
            pairs={"Dana": {"Alice": 5, "Bob": 0}},
            last_run=None
        )
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={}
        )
        
        assert "Bob" in selected[0] or selected[0] == "Bob"
