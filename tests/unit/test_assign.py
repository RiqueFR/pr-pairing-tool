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


class TestBucketAssignment:
    def test_bucket_assignments_balanced_load(self):
        developers = [
            Developer(name="Alice", can_review=True),
            Developer(name="Bob", can_review=True),
            Developer(name="Charlie", can_review=True),
            Developer(name="Dana", can_review=True),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE,
            balance_mode=True
        )
        
        review_counts = {}
        for dev in developers:
            for reviewer in dev.reviewers:
                review_counts[reviewer] = review_counts.get(reviewer, 0) + 1
        
        max_reviews = max(review_counts.values())
        min_reviews = min(review_counts.values())
        assert max_reviews - min_reviews <= 1

    def test_bucket_team_coverage(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend"),
            Developer(name="Bob", can_review=True, team="frontend"),
            Developer(name="Charlie", can_review=True, team="backend"),
            Developer(name="Dana", can_review=True, team="backend"),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=2,
            team_mode=True,
            knowledge_mode=KnowledgeMode.ANYONE,
            balance_mode=True
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        bob = next(d for d in developers if d.name == "Bob")
        
        assert "Bob" in alice.reviewers
        assert "Alice" in bob.reviewers

    def test_bucket_with_unbalanced_teams(self):
        developers = [
            Developer(name="Alice", can_review=True, team="team1"),
            Developer(name="Bob", can_review=True, team="team1"),
            Developer(name="Charlie", can_review=True, team="team2"),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=2,
            team_mode=True,
            knowledge_mode=KnowledgeMode.ANYONE,
            balance_mode=True
        )
        
        charlie = next(d for d in developers if d.name == "Charlie")
        assert len(charlie.reviewers) == 2
        
        team1_devs = [d for d in developers if d.team == "team1"]
        for dev in team1_devs:
            assert len(dev.reviewers) == 2

    def test_bucket_no_reviewers_available_warning(self):
        developers = [
            Developer(name="Alice", can_review=True),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=2,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE,
            balance_mode=True
        )
        
        assert len(warnings) > 0
        assert "No reviewers available" in warnings[0]

    def test_bucket_with_knowledge_mode(self):
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
            knowledge_mode=KnowledgeMode.EXPERTS_ONLY,
            balance_mode=True
        )
        
        bob = next(d for d in developers if d.name == "Bob")
        assert "Alice" in bob.reviewers

    def test_bucket_updates_history(self):
        developers = [
            Developer(name="Alice", can_review=True),
            Developer(name="Bob", can_review=True),
        ]
        history = History(pairs={}, last_run=None)
        
        assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE,
            balance_mode=True
        )
        
        assert "Alice" in history.pairs
        assert "Bob" in history.pairs["Alice"]
        assert history.pairs["Alice"]["Bob"] == 1
