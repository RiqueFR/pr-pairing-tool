import csv
import json
import tempfile
from pathlib import Path

import pytest

from pr_pairing import (
    load_csv,
    save_csv,
    load_history,
    save_history,
    load_developers,
    save_developers,
    normalize_bool,
    get_pair_count,
    get_total_reviews_assigned,
    update_history,
    select_reviewers,
    assign_reviewers,
    KnowledgeMode,
    History,
    Developer,
    load_exclusions_from_csv,
    load_exclusions_from_yaml,
    parse_exclusion_string,
    parse_exclusions_cli,
    find_config_file,
    load_config,
    merge_config,
)
from pr_pairing.cli import parse_arguments


class TestParseArgs:
    def test_default_reviewers(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path]
            
            args = parse_arguments()
            args = merge_config({}, args)
            
            assert args.reviewers == 2
            assert args.team_mode is False
            assert args.knowledge_mode == KnowledgeMode.ANYONE.value
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)

    def test_custom_reviewers(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path, '-r', '4']
            
            args = parse_arguments()
            
            assert args.reviewers == 4
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)

    def test_team_mode_flag(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path, '-t']
            
            args = parse_arguments()
            
            assert args.team_mode is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)

    def test_knowledge_mode_choices(self):
        modes = [
            (KnowledgeMode.ANYONE, "anyone"),
            (KnowledgeMode.EXPERTS_ONLY, "experts-only"),
            (KnowledgeMode.MENTORSHIP, "mentorship"),
            (KnowledgeMode.SIMILAR_LEVELS, "similar-levels"),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            
            for enum_mode, str_mode in modes:
                sys.argv = ['pr_pairing.py', '-i', temp_path, '-k', str_mode]
                args = parse_arguments()
                assert args.knowledge_mode == enum_mode.value
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)


class TestDeveloperModel:
    def test_developer_to_dict(self):
        dev = Developer(
            name="Alice",
            can_review=True,
            team="frontend",
            knowledge_level=5,
            reviewers=["Bob", "Charlie"]
        )
        
        d = dev.to_dict()
        
        assert d["name"] == "Alice"
        assert d["can_review"] == True
        assert d["team"] == "frontend"
        assert d["knowledge_level"] == 5
        assert d["reviewers"] == "Bob, Charlie"

    def test_developer_to_dict_with_metadata(self):
        dev = Developer(
            name="Alice",
            can_review=True,
            team="frontend",
            knowledge_level=5,
            reviewers=["Bob"],
            metadata={"email": "alice@example.com"}
        )
        
        d = dev.to_dict()
        
        assert d["name"] == "Alice"
        assert d["email"] == "alice@example.com"


class TestCSVFunctions:
    def test_load_csv_basic(self, basic_csv_content):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(basic_csv_content)
            temp_path = f.name

        try:
            rows = load_csv(temp_path)
            
            assert len(rows) == 4
            assert rows[0]["name"] == "Alice"
            assert rows[0]["can_review"] == "true"
        finally:
            import os
            os.unlink(temp_path)

    def test_load_csv_missing_optional_columns(self):
        content = "name,can_review\nAlice,true"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            rows = load_csv(temp_path)
            
            assert len(rows) == 1
            assert "team" not in rows[0]
            assert "knowledge_level" not in rows[0]
        finally:
            import os
            os.unlink(temp_path)

    def test_save_csv_adds_reviewers_column(self, temp_csv):
        rows = load_csv(temp_csv)
        
        for row in rows:
            row["reviewers"] = "test"
        
        fieldnames = list(rows[0].keys())
        
        save_csv(temp_csv, rows, fieldnames)
        
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            saved_rows = list(reader)
        
        assert "reviewers" in saved_rows[0]


class TestLoadDevelopers:
    def test_load_developers_basic(self):
        content = "name,can_review,team,knowledge_level\nAlice,true,frontend,5\nBob,true,backend,3"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            developers = load_developers(temp_path)
            
            assert len(developers) == 2
            assert developers[0].name == "Alice"
            assert developers[0].can_review == True
            assert developers[0].team == "frontend"
            assert developers[0].knowledge_level == 5
            assert developers[1].name == "Bob"
            assert developers[1].knowledge_level == 3
        finally:
            import os
            os.unlink(temp_path)

    def test_load_developers_normalizes_can_review(self):
        content = "name,can_review\nAlice,True\nBob,false\nCharlie,yes"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            developers = load_developers(temp_path)
            
            assert developers[0].can_review == True
            assert developers[1].can_review == False
            assert developers[2].can_review == True
        finally:
            import os
            os.unlink(temp_path)

    def test_load_developers_parses_knowledge_level(self):
        content = "name,can_review,knowledge_level\nAlice,3\nBob,invalid\nCharlie,"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            developers = load_developers(temp_path)
            
            assert developers[0].knowledge_level == 3
            assert developers[1].knowledge_level == 3  # default
            assert developers[2].knowledge_level == 3  # default
        finally:
            import os
            os.unlink(temp_path)


class TestSaveDevelopers:
    def test_save_developers(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=5, reviewers=["Bob"]),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3, reviewers=[]),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review,team,knowledge_level\n")
            temp_path = f.name

        try:
            save_developers(temp_path, developers)
            
            devs = load_developers(temp_path)
            assert len(devs) == 2
            assert devs[0].reviewers == ["Bob"]
        finally:
            import os
            os.unlink(temp_path)


class TestHistoryFunctions:
    def test_load_nonexistent_history(self):
        import os
        temp_path = "/tmp/nonexistent_history_12345.json"
        
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        
        history = load_history(temp_path)
        
        assert history.pairs == {}
        assert history.last_run is None

    def test_load_existing_history(self, sample_history):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_history.to_dict(), f)
            temp_path = f.name

        try:
            history = load_history(temp_path)
            
            assert hasattr(history, 'pairs')
            assert "Alice" in history.pairs
            assert history.pairs["Alice"]["Bob"] == 2
        finally:
            import os
            os.unlink(temp_path)

    def test_save_history_with_timestamp(self, temp_history):
        history = load_history(temp_history)
        
        save_history(temp_history, history)
        
        with open(temp_history, 'r') as f:
            saved = json.load(f)
        
        assert saved["last_run"] is not None
        assert "Z" in saved["last_run"] or "+00:00" in saved["last_run"]


class TestUtilityFunctions:
    @pytest.mark.parametrize("value,expected", [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("y", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("n", False),
    ])
    def test_normalize_bool(self, value, expected):
        assert normalize_bool(value) == expected

    def test_normalize_bool_boolean_input(self):
        assert normalize_bool(True) is True
        assert normalize_bool(False) is False


class TestHistoryTracking:
    def test_get_pair_count(self, sample_history):
        assert get_pair_count(sample_history, "Alice", "Bob") == 2
        assert get_pair_count(sample_history, "Alice", "Dana") == 0
        assert get_pair_count(sample_history, "Unknown", "Bob") == 0

    def test_get_total_reviews_assigned(self, sample_history):
        assert get_total_reviews_assigned(sample_history, "Bob") == 2
        assert get_total_reviews_assigned(sample_history, "Charlie") == 1
        assert get_total_reviews_assigned(sample_history, "Unknown") == 0

    def test_update_history(self, empty_history):
        update_history(empty_history, "Alice", ["Bob", "Charlie"])
        
        assert "Alice" in empty_history.pairs
        assert empty_history.pairs["Alice"]["Bob"] == 1
        assert empty_history.pairs["Alice"]["Charlie"] == 1

    def test_update_history_increments_existing(self):
        history = History(
            pairs={"Alice": {"Bob": 2}},
            last_run=None
        )
        
        update_history(history, "Alice", ["Bob"])
        
        assert history.pairs["Alice"]["Bob"] == 3


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

    def test_similar_levels_sorts_by_knowledge_diff(self):
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


class TestFindConfigFile:
    def test_find_config_explicit_path_exists(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("reviewers: 3\n")
            temp_path = f.name
        
        try:
            result = find_config_file(temp_path)
            assert result is not None
            assert result.name == Path(temp_path).name
        finally:
            import os
            os.unlink(temp_path)
    
    def test_find_config_explicit_path_not_exists(self):
        result = find_config_file("/nonexistent/config.yaml")
        assert result is None
    
    def test_find_config_no_path_returns_none_when_no_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = find_config_file(None)
        assert result is None
    
    def test_find_config_searches_prpairingrc(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".prpairingrc"
        config_file.write_text("reviewers: 3\n")
        
        monkeypatch.chdir(tmp_path)
        result = find_config_file(None)
        assert result is not None
        assert result.name == ".prpairingrc"
    
    def test_find_config_searches_pr_pairing_yaml(self, tmp_path, monkeypatch):
        config_file = tmp_path / "pr_pairing.yaml"
        config_file.write_text("reviewers: 3\n")
        
        monkeypatch.chdir(tmp_path)
        result = find_config_file(None)
        assert result is not None
        assert result.name == "pr_pairing.yaml"
    
    def test_find_config_prpairingrc_priority_over_yaml(self, tmp_path, monkeypatch):
        config_file1 = tmp_path / ".prpairingrc"
        config_file1.write_text("reviewers: 3\n")
        config_file2 = tmp_path / "pr_pairing.yaml"
        config_file2.write_text("reviewers: 5\n")
        
        monkeypatch.chdir(tmp_path)
        result = find_config_file(None)
        assert result is not None
        assert result.name == ".prpairingrc"


class TestLoadConfig:
    def test_load_config_basic(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("reviewers: 3\nteam_mode: true\n")
            temp_path = f.name
        
        try:
            config = load_config(Path(temp_path))
            assert config["reviewers"] == 3
            assert config["team_mode"] is True
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_config_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = f.name
        
        try:
            config = load_config(Path(temp_path))
            assert config == {}
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_config_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [\n")
            temp_path = f.name
        
        try:
            from pr_pairing import FileError
            with pytest.raises(FileError):
                load_config(Path(temp_path))
        finally:
            import os
            os.unlink(temp_path)


class TestMergeConfig:
    def test_merge_config_reviewers(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"reviewers": 4}
            args = merge_config(config, args)
            
            assert args.reviewers == 4
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_team_mode_string(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"team_mode": "true"}
            args = merge_config(config, args)
            
            assert args.team_mode is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_knowledge_mode(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"knowledge_mode": "mentorship"}
            args = merge_config(config, args)
            
            assert args.knowledge_mode == "mentorship"
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_history(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"history": "./custom_history.json"}
            args = merge_config(config, args)
            
            assert args.history == "./custom_history.json"
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_verbose_bool(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"verbose": True}
            args = merge_config(config, args)
            
            assert args.verbose == 1
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_verbose_int(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv]
            
            args = parse_arguments()
            
            config = {"verbose": 2}
            args = merge_config(config, args)
            
            assert args.verbose == 2
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_cli_overrides_config(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv, '-r', '5']
            
            args = parse_arguments()
            
            config = {"reviewers": 3}
            args = merge_config(config, args)
            
            assert args.reviewers == 5
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)
    
    def test_merge_config_cli_team_mode_overrides_config(self):
        import sys
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_csv = f.name
        
        try:
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_csv, '-t']
            
            args = parse_arguments()
            
            config = {"team_mode": False}
            args = merge_config(config, args)
            
            assert args.team_mode is True
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_csv)


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
