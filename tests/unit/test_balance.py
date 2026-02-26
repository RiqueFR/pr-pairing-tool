import tempfile

import pytest

from pr_pairing import assign_reviewers, select_reviewers, KnowledgeMode, Developer, History
from pr_pairing.cli import parse_arguments, merge_config


class TestBalanceMode:
    def test_no_balance_flag_default(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path]
            
            args = parse_arguments()
            
            assert args.no_balance is False
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)

    def test_no_balance_flag_explicit(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path, '--no-balance']
            
            args = parse_arguments()
            
            assert args.no_balance is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)

    def test_balance_mode_distributes_evenly(self):
        developers = [
            Developer(name="Alice", can_review=True),
            Developer(name="Bob", can_review=True),
            Developer(name="Charlie", can_review=True),
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
        
        total_reviews = sum(review_counts.values())
        assert total_reviews == 3
        
        max_reviews = max(review_counts.values())
        min_reviews = min(review_counts.values())
        assert max_reviews - min_reviews <= 1

    def test_balance_mode_with_2_reviewers_per_dev(self):
        developers = [
            Developer(name="Alice", can_review=True),
            Developer(name="Bob", can_review=True),
            Developer(name="Charlie", can_review=True),
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
        
        review_counts = {}
        for dev in developers:
            for reviewer in dev.reviewers:
                review_counts[reviewer] = review_counts.get(reviewer, 0) + 1
        
        total_reviews = sum(review_counts.values())
        assert total_reviews == 6
        
        max_reviews = max(review_counts.values())
        min_reviews = min(review_counts.values())
        assert max_reviews - min_reviews <= 1

    def test_no_balance_mode_team_priority(self):
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
            knowledge_mode=KnowledgeMode.ANYONE,
            balance_mode=False
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        assert "Bob" in alice.reviewers

    def test_balance_mode_with_team_mode(self):
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

    def test_balance_mode_considers_current_assignments(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True)
        history = History(pairs={}, last_run=None)
        current_assignments = {"Alice": 2, "Bob": 0, "Charlie": 0}
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments=current_assignments,
            balance_mode=True
        )
        
        assert "Bob" in selected
        assert "Charlie" in selected
        assert "Alice" not in selected

    def test_select_reviewers_balance_mode_default(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True)
        history = History(pairs={}, last_run=None)
        current_assignments = {"Alice": 2, "Bob": 0, "Charlie": 0}
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments=current_assignments,
            balance_mode=True
        )
        
        assert "Bob" in selected
        assert "Charlie" in selected
        assert "Alice" not in selected

    def test_select_reviewers_no_balance_mode(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True)
        history = History(pairs={}, last_run=None)
        current_assignments = {"Alice": 2, "Bob": 0, "Charlie": 0}
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments=current_assignments,
            balance_mode=False
        )
        
        assert len(selected) == 2
        assert "Alice" in selected or "Bob" in selected or "Charlie" in selected

    def test_merge_config_no_balance(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"no_balance": True}
            args = merge_config(config, args)
            
            assert args.no_balance is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
