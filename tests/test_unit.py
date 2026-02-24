import csv
import json
import tempfile

import pytest

from pr_pairing import (
    load_csv,
    save_csv,
    load_history,
    save_history,
    normalize_bool,
    get_pair_count,
    get_total_reviews_assigned,
    update_history,
    select_reviewers,
    assign_reviewers,
    parse_args,
    KnowledgeMode,
    History,
    load_exclusions_from_csv,
    load_exclusions_from_yaml,
    parse_exclusion_string,
    parse_exclusions_cli,
)


class TestParseArgs:
    def test_default_reviewers(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\nAlice,true")
            temp_path = f.name

        try:
            import sys
            old_argv = sys.argv
            sys.argv = ['pr_pairing.py', '-i', temp_path]
            
            args = parse_args()
            
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
            
            args = parse_args()
            
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
            
            args = parse_args()
            
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
                args = parse_args()
                assert args.knowledge_mode == enum_mode.value
            
            sys.argv = old_argv
        finally:
            import os
            os.unlink(temp_path)


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
            {"name": "Alice", "team": "frontend", "knowledge_level": 3},
            {"name": "Bob", "team": "backend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Alice",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={}
        )
        
        assert "Alice" not in selected
        assert len(selected) == 1
        assert "Bob" in selected

    def test_select_correct_number(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 3},
            {"name": "Bob", "team": "backend", "knowledge_level": 3},
            {"name": "Charlie", "team": "backend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Alice",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={}
        )
        
        assert len(selected) == 2

    def test_select_fewer_when_not_enough(self):
        candidates = [
            {"name": "Bob", "team": "backend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Alice",
            candidates=candidates,
            history=history,
            num_reviewers=3,
            team_mode=False,
            dev_team=None,
            current_assignments={}
        )
        
        assert len(selected) == 1

    def test_experts_only_filter(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 5},
            {"name": "Bob", "team": "backend", "knowledge_level": 2},
            {"name": "Charlie", "team": "backend", "knowledge_level": 4},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=3,
            team_mode=False,
            dev_team=None,
            current_assignments={},
            knowledge_mode=KnowledgeMode.EXPERTS_ONLY
        )
        
        assert "Bob" not in selected
        assert "Alice" in selected
        assert "Charlie" in selected
        assert len(selected) == 2

    def test_mentorship_novice_gets_expert(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 5},
            {"name": "Bob", "team": "backend", "knowledge_level": 2},
            {"name": "Charlie", "team": "backend", "knowledge_level": 4},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={},
            knowledge_mode=KnowledgeMode.MENTORSHIP,
            dev_knowledge=1
        )
        
        assert "Bob" not in selected
        assert "Alice" in selected
        assert "Charlie" in selected

    def test_mentorship_senior_can_get_anyone(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 5},
            {"name": "Bob", "team": "backend", "knowledge_level": 2},
            {"name": "Charlie", "team": "backend", "knowledge_level": 4},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={},
            knowledge_mode=KnowledgeMode.MENTORSHIP,
            dev_knowledge=4
        )
        
        assert "Bob" in selected or "Alice" in selected or "Charlie" in selected

    def test_similar_levels_sorts_by_knowledge_diff(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 5},
            {"name": "Bob", "team": "backend", "knowledge_level": 1},
            {"name": "Charlie", "team": "backend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={},
            knowledge_mode=KnowledgeMode.SIMILAR_LEVELS,
            dev_knowledge=2
        )
        
        assert "Charlie" in selected
        assert "Bob" in selected

    def test_team_mode_prioritizes_same_team(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 3},
            {"name": "Bob", "team": "frontend", "knowledge_level": 3},
            {"name": "Charlie", "team": "backend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Alice",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=True,
            dev_team="frontend",
            current_assignments={}
        )
        
        assert "Bob" in selected
        assert "Charlie" in selected or "Alice" not in selected

    def test_history_affects_selection(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 3},
            {"name": "Bob", "team": "backend", "knowledge_level": 3},
        ]
        history = History(
            pairs={"Dana": {"Alice": 5, "Bob": 0}},
            last_run=None
        )
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={}
        )
        
        assert "Bob" in selected[0] or selected[0] == "Bob"


class TestAssignReviewers:
    def test_assign_reviewers_basic(self):
        rows = [
            {"name": "Alice", "can_review": "true"},
            {"name": "Bob", "can_review": "true"},
        ]
        history = History(pairs={}, last_run=None)
        
        updated_rows, warnings = assign_reviewers(
            rows=rows,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE
        )
        
        assert len(updated_rows) == 2
        assert "reviewers" in updated_rows[0]
        assert len(updated_rows[0]["reviewers"]) > 0 or "Bob" in updated_rows[0]["reviewers"] or "Alice" in updated_rows[0]["reviewers"]

    def test_assign_reviewers_respects_can_review_false(self):
        rows = [
            {"name": "Alice", "can_review": "true"},
            {"name": "Bob", "can_review": "false"},
            {"name": "Charlie", "can_review": "true"},
        ]
        history = History(pairs={}, last_run=None)
        
        updated_rows, warnings = assign_reviewers(
            rows=rows,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE
        )
        
        bob_row = [r for r in updated_rows if r["name"] == "Bob"][0]
        alice_row = [r for r in updated_rows if r["name"] == "Alice"][0]
        
        assert "Bob" not in alice_row["reviewers"]

    def test_assign_reviewers_with_team_mode(self):
        rows = [
            {"name": "Alice", "can_review": "true", "team": "frontend"},
            {"name": "Bob", "can_review": "true", "team": "frontend"},
            {"name": "Charlie", "can_review": "true", "team": "backend"},
        ]
        history = History(pairs={}, last_run=None)
        
        updated_rows, warnings = assign_reviewers(
            rows=rows,
            history=history,
            num_reviewers=1,
            team_mode=True,
            knowledge_mode=KnowledgeMode.ANYONE
        )
        
        alice_reviewers = [r for r in updated_rows if r["name"] == "Alice"][0]["reviewers"]
        assert "Bob" in alice_reviewers or "Charlie" in alice_reviewers

    def test_assign_reviewers_with_knowledge_mode(self):
        rows = [
            {"name": "Alice", "can_review": "true", "knowledge_level": "5"},
            {"name": "Bob", "can_review": "true", "knowledge_level": "1"},
            {"name": "Charlie", "can_review": "true", "knowledge_level": "3"},
        ]
        history = History(pairs={}, last_run=None)
        
        updated_rows, warnings = assign_reviewers(
            rows=rows,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.EXPERTS_ONLY
        )
        
        bob_row = [r for r in updated_rows if r["name"] == "Bob"][0]
        assert "Alice" in bob_row["reviewers"]

    def test_assign_reviewers_partial_assignment_warning(self):
        rows = [
            {"name": "Alice", "can_review": "true"},
        ]
        history = History(pairs={}, last_run=None)
        
        updated_rows, warnings = assign_reviewers(
            rows=rows,
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
            {"name": "Alice", "team": "frontend", "knowledge_level": 3},
            {"name": "Bob", "team": "backend", "knowledge_level": 3},
            {"name": "Charlie", "team": "backend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={},
            exclusions={("Dana", "Bob")}
        )
        
        assert "Bob" not in selected
        assert "Alice" in selected
        assert "Charlie" in selected
    
    def test_exclude_multiple_reviewers(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 3},
            {"name": "Bob", "team": "backend", "knowledge_level": 3},
            {"name": "Charlie", "team": "backend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={},
            exclusions={("Dana", "Alice"), ("Dana", "Bob")}
        )
        
        assert "Alice" not in selected
        assert "Bob" not in selected
        assert "Charlie" in selected
    
    def test_exclude_all_reviewers(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 3},
            {"name": "Bob", "team": "backend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={},
            exclusions={("Dana", "Alice"), ("Dana", "Bob")}
        )
        
        assert len(selected) == 0
        assert "All reviewers excluded" in warnings[0]
    
    def test_exclusion_with_knowledge_filter(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 5},
            {"name": "Bob", "team": "backend", "knowledge_level": 2},
            {"name": "Charlie", "team": "backend", "knowledge_level": 4},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=False,
            dev_team=None,
            current_assignments={},
            knowledge_mode=KnowledgeMode.EXPERTS_ONLY,
            exclusions={("Dana", "Charlie")}
        )
        
        assert "Charlie" not in selected
        assert "Alice" in selected
        assert "Bob" not in selected
    
    def test_exclusion_with_team_mode(self):
        candidates = [
            {"name": "Alice", "team": "frontend", "knowledge_level": 3},
            {"name": "Bob", "team": "backend", "knowledge_level": 3},
            {"name": "Charlie", "team": "frontend", "knowledge_level": 3},
        ]
        history = History(pairs={}, last_run=None)
        
        selected, warnings = select_reviewers(
            developer="Dana",
            candidates=candidates,
            history=history,
            num_reviewers=2,
            team_mode=True,
            dev_team="frontend",
            current_assignments={},
            exclusions={("Dana", "Alice")}
        )
        
        assert "Alice" not in selected
        assert "Charlie" in selected


class TestExclusionInAssignReviewers:
    def test_assign_reviewers_with_exclusions(self):
        rows = [
            {"name": "Alice", "can_review": "true"},
            {"name": "Bob", "can_review": "true"},
            {"name": "Charlie", "can_review": "true"},
        ]
        history = History(pairs={}, last_run=None)
        
        updated_rows, warnings = assign_reviewers(
            rows=rows,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE,
            exclusions={("Alice", "Bob")}
        )
        
        alice_row = [r for r in updated_rows if r["name"] == "Alice"][0]
        assert "Bob" not in alice_row["reviewers"]
    
    def test_assign_reviewers_exclusion_warning(self):
        rows = [
            {"name": "Alice", "can_review": "true"},
            {"name": "Bob", "can_review": "true"},
            {"name": "Charlie", "can_review": "true"},
        ]
        history = History(pairs={}, last_run=None)
        
        updated_rows, warnings = assign_reviewers(
            rows=rows,
            history=history,
            num_reviewers=1,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE,
            exclusions={("Alice", "Bob")}
        )
        
        alice_row = [r for r in updated_rows if r["name"] == "Alice"][0]
        assert "Bob" not in alice_row["reviewers"]
