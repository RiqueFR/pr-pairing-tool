import tempfile

import pytest

from pr_pairing import (
    load_exclusions_from_csv,
    load_exclusions_from_yaml,
    parse_exclusion_string,
    parse_exclusions_cli,
    select_reviewers,
    assign_reviewers,
    KnowledgeMode,
    Developer,
    History,
)


class TestExclusionFunctions:
    def test_parse_exclusion_string_valid(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_exclusion_string("Alice:Bob", valid_developers)
        assert result == ("Alice", "Bob")
    
    def test_parse_exclusion_string_invalid_no_colon(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_exclusion_string("AliceBob", valid_developers)
        assert result is None
    
    def test_parse_exclusion_string_nonexistent_developer(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_exclusion_string("Alice:David", valid_developers)
        assert result is None
    
    def test_parse_exclusion_string_empty(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_exclusion_string("", valid_developers)
        assert result is None
    
    def test_parse_exclusion_string_empty_after_strip(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_exclusion_string("Alice:  ", valid_developers)
        assert result is None
    
    def test_parse_exclusions_cli_multiple(self):
        valid_developers = {"Alice", "Bob", "Charlie", "Dana"}
        exclusions = ["Alice:Bob", "Charlie:Dana"]
        
        result = parse_exclusions_cli(exclusions, valid_developers)
        assert result == {("Alice", "Bob"), ("Charlie", "Dana")}
    
    def test_parse_exclusions_cli_skips_invalid(self):
        valid_developers = {"Alice", "Bob", "Charlie", "Dana"}
        exclusions = ["Alice:Bob", "Invalid:David", "Charlie:Dana"]
        
        result = parse_exclusions_cli(exclusions, valid_developers)
        assert result == {("Alice", "Bob"), ("Charlie", "Dana")}
    
    def test_load_exclusions_from_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("developer,excluded_reviewer\n")
            f.write("Alice,Bob\n")
            f.write("Bob,Alice\n")
            f.write("Charlie,Dana\n")
            temp_path = f.name
        
        try:
            exclusions = load_exclusions_from_csv(temp_path)
            assert ("Alice", "Bob") in exclusions
            assert ("Bob", "Alice") in exclusions
            assert ("Charlie", "Dana") in exclusions
            assert len(exclusions) == 3
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_exclusions_from_csv_empty(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("developer,excluded_reviewer\n")
            temp_path = f.name
        
        try:
            exclusions = load_exclusions_from_csv(temp_path)
            assert len(exclusions) == 0
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_exclusions_from_yaml(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("exclusions:\n")
            f.write("  - developers: [Alice, Bob]\n")
            f.write("  - developers: [Charlie, Dana]\n")
            temp_path = f.name
        
        try:
            exclusions = load_exclusions_from_yaml(temp_path)
            assert ("Alice", "Bob") in exclusions
            assert ("Bob", "Alice") in exclusions
            assert ("Charlie", "Dana") in exclusions
            assert ("Dana", "Charlie") in exclusions
            assert len(exclusions) == 4
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_exclusions_from_yaml_empty(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("exclusions: []\n")
            temp_path = f.name
        
        try:
            exclusions = load_exclusions_from_yaml(temp_path)
            assert len(exclusions) == 0
        finally:
            import os
            os.unlink(temp_path)


class TestExclusionInSelectReviewers:
    def test_exclude_single_reviewer(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            exclusions={("Dana", "Bob")}
        )
        
        assert "Bob" not in selected
        assert "Alice" in selected
        assert "Charlie" in selected
    
    def test_exclude_multiple_reviewers(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
            Developer(name="Charlie", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            exclusions={("Dana", "Alice"), ("Dana", "Bob")}
        )
        
        assert "Alice" not in selected
        assert "Bob" not in selected
        assert "Charlie" in selected
    
    def test_exclude_all_reviewers(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True)
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            exclusions={("Dana", "Alice"), ("Dana", "Bob")}
        )
        
        assert len(selected) == 0
        assert "All reviewers excluded" in warnings[0]
    
    def test_exclusion_with_knowledge_filter(self):
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
            num_reviewers=2,
            team_mode=False,
            current_assignments={},
            knowledge_mode=KnowledgeMode.EXPERTS_ONLY,
            exclusions={("Dana", "Charlie")}
        )
        
        assert "Charlie" not in selected
        assert "Alice" in selected
        assert "Bob" not in selected
    
    def test_exclusion_with_team_mode(self):
        candidates = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3),
            Developer(name="Charlie", can_review=True, team="frontend", knowledge_level=3),
        ]
        dev = Developer(name="Dana", can_review=True, team="frontend")
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            dev=dev,
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=True,
            current_assignments={},
            exclusions={("Dana", "Alice")}
        )
        
        assert "Alice" not in selected
        assert "Charlie" in selected


class TestExclusionInAssignReviewers:
    def test_assign_reviewers_with_exclusions(self):
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
            exclusions={("Alice", "Bob")}
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        assert "Bob" not in alice.reviewers
    
    def test_assign_reviewers_exclusion_warning(self):
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
            exclusions={("Alice", "Bob")}
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        assert "Bob" not in alice.reviewers
