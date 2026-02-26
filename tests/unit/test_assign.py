import pytest

from pr_pairing import assign_reviewers, KnowledgeMode, Developer, History


class TestAssignReviewers:
    def test_assign_reviewers_basic(self):
        developers = [
            Developer(name="Alice", can_review=True),
            Developer(name="Bob", can_review=True),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE
        )
        
        assert len(developers) == 2
        assert developers[0].reviewers or developers[1].reviewers

    def test_assign_reviewers_respects_can_review_false(self):
        developers = [
            Developer(name="Alice", can_review=True),
            Developer(name="Bob", can_review=False),
            Developer(name="Charlie", can_review=True),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        assert "Bob" not in alice.reviewers

    def test_assign_reviewers_with_team_mode(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend"),
            Developer(name="Bob", can_review=True, team="frontend"),
            Developer(name="Charlie", can_review=True, team="backend"),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=1,
            team_mode=True,
            knowledge_mode=KnowledgeMode.ANYONE
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        assert "Bob" in alice.reviewers or "Charlie" in alice.reviewers

    def test_assign_reviewers_with_knowledge_mode(self):
        developers = [
            Developer(name="Alice", can_review=True, knowledge_level=5),
            Developer(name="Bob", can_review=True, knowledge_level=1),
            Developer(name="Charlie", can_review=True, knowledge_level=3),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.EXPERTS_ONLY
        )
        
        bob = next(d for d in developers if d.name == "Bob")
        assert "Alice" in bob.reviewers

    def test_assign_reviewers_partial_assignment_warning(self):
        developers = [
            Developer(name="Alice", can_review=True),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=3,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE
        )
        
        assert len(warnings) > 0
