import tempfile

import pytest

from pr_pairing.requirements import (
    parse_requirement_string,
    load_requirements_from_csv,
    load_requirements_from_yaml,
    load_requirements,
    parse_requirements_cli,
    check_conflicts,
)
from pr_pairing import (
    select_reviewers,
    assign_reviewers,
    KnowledgeMode,
    Developer,
    History,
)


class TestRequirementsFunctions:
    def test_parse_requirement_string_valid(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_requirement_string("Bob:Alice", valid_developers)
        assert result == ("Bob", "Alice")
    
    def test_parse_requirement_string_invalid_no_colon(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_requirement_string("BobAlice", valid_developers)
        assert result is None
    
    def test_parse_requirement_string_nonexistent_developer(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_requirement_string("Bob:David", valid_developers)
        assert result is None
    
    def test_parse_requirement_string_nonexistent_reviewer(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_requirement_string("David:Alice", valid_developers)
        assert result is None
    
    def test_parse_requirement_string_empty(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_requirement_string("", valid_developers)
        assert result is None
    
    def test_parse_requirement_string_empty_after_strip(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_requirement_string("Bob:  ", valid_developers)
        assert result is None
    
    def test_parse_requirement_string_self_requirement(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        result = parse_requirement_string("Alice:Alice", valid_developers)
        assert result is None
    
    def test_parse_requirements_cli_multiple(self):
        valid_developers = {"Alice", "Bob", "Charlie", "Dana"}
        requirements = ["Bob:Alice", "Bob:Charlie"]
        
        result = parse_requirements_cli(requirements, valid_developers)
        assert result == {"Bob": ["Alice", "Charlie"]}
    
    def test_parse_requirements_cli_skips_invalid(self):
        valid_developers = {"Alice", "Bob", "Charlie", "Dana"}
        requirements = ["Bob:Alice", "Invalid:David", "Bob:Charlie"]
        
        result = parse_requirements_cli(requirements, valid_developers)
        assert result == {"Bob": ["Alice", "Charlie"]}
    
    def test_load_requirements_from_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("developer,required_reviewer\n")
            f.write("Bob,Alice\n")
            f.write("Bob,Charlie\n")
            f.write("Dana,Alice\n")
            temp_path = f.name
        
        try:
            requirements = load_requirements_from_csv(temp_path)
            assert requirements == {"Bob": ["Alice", "Charlie"], "Dana": ["Alice"]}
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_requirements_from_csv_empty(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("developer,required_reviewer\n")
            temp_path = f.name
        
        try:
            requirements = load_requirements_from_csv(temp_path)
            assert requirements == {}
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_requirements_from_yaml(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("requirements:\n")
            f.write("  - developer: Bob\n")
            f.write("    required_reviewers:\n")
            f.write("      - Alice\n")
            f.write("      - Charlie\n")
            f.write("  - developer: Dana\n")
            f.write("    required_reviewers:\n")
            f.write("      - Alice\n")
            temp_path = f.name
        
        try:
            requirements = load_requirements_from_yaml(temp_path)
            assert requirements == {"Bob": ["Alice", "Charlie"], "Dana": ["Alice"]}
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_requirements_from_yaml_empty(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("requirements: []\n")
            temp_path = f.name
        
        try:
            requirements = load_requirements_from_yaml(temp_path)
            assert requirements == {}
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_requirements_validates_developers(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("developer,required_reviewer\n")
            f.write("Invalid,Alice\n")
            temp_path = f.name
        
        try:
            with pytest.raises(Exception):
                load_requirements(temp_path, valid_developers)
        finally:
            import os
            os.unlink(temp_path)
    
    def test_load_requirements_validates_reviewers(self):
        valid_developers = {"Alice", "Bob", "Charlie"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("developer,required_reviewer\n")
            f.write("Bob,Invalid\n")
            temp_path = f.name
        
        try:
            with pytest.raises(Exception):
                load_requirements(temp_path, valid_developers)
        finally:
            import os
            os.unlink(temp_path)


class TestCheckConflicts:
    def test_no_conflicts(self):
        requirements = {"Bob": ["Alice", "Charlie"]}
        exclusions = {("Dana", "Eve")}
        
        conflicts = check_conflicts(requirements, exclusions)
        assert len(conflicts) == 0
    
    def test_conflict_detected(self):
        requirements = {"Bob": ["Alice"]}
        exclusions = {("Bob", "Alice")}
        
        conflicts = check_conflicts(requirements, exclusions)
        assert len(conflicts) == 1
        assert "Conflict" in conflicts[0]
    
    def test_multiple_conflicts(self):
        requirements = {"Bob": ["Alice", "Charlie"], "Dana": ["Eve"]}
        exclusions = {("Bob", "Alice"), ("Dana", "Eve")}
        
        conflicts = check_conflicts(requirements, exclusions)
        assert len(conflicts) == 2


class TestRequirementsInAssignReviewers:
    def test_assign_reviewers_with_requirements(self):
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
            requirements={"Alice": ["Bob"]}
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        assert "Bob" in alice.reviewers
    
    def test_assign_reviewers_with_requirements_team_mode(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend"),
            Developer(name="Bob", can_review=True, team="frontend"),
            Developer(name="Charlie", can_review=True, team="backend"),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=2,
            team_mode=True,
            knowledge_mode=KnowledgeMode.ANYONE,
            requirements={"Alice": ["Bob"]}
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        assert "Bob" in alice.reviewers
    
    def test_assign_reviewers_requirement_for_non_reviewer(self):
        developers = [
            Developer(name="Alice", can_review=True),
            Developer(name="Bob", can_review=False),
            Developer(name="Charlie", can_review=True),
        ]
        history = History(pairs={}, last_run=None)
        
        warnings = assign_reviewers(
            developers=developers,
            history=history,
            num_reviewers=2,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE,
            requirements={"Alice": ["Bob"]}
        )
        
        assert any("Cannot fulfill requirement" in w for w in warnings)
    
    def test_assign_reviewers_self_requirement(self):
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
            requirements={"Alice": ["Alice"]}
        )
        
        assert any("Skipping self-requirement" in w for w in warnings)
    
    def test_assign_reviewers_multiple_requirements(self):
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
            num_reviewers=2,
            team_mode=False,
            knowledge_mode=KnowledgeMode.ANYONE,
            requirements={
                "Alice": ["Bob"],
                "Charlie": ["Dana"]
            }
        )
        
        alice = next(d for d in developers if d.name == "Alice")
        charlie = next(d for d in developers if d.name == "Charlie")
        assert "Bob" in alice.reviewers
        assert "Dana" in charlie.reviewers
