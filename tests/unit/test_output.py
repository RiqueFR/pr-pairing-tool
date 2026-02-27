import json
import tempfile
import pytest

from pr_pairing import Developer
from pr_pairing.output import (
    format_output_json,
    format_output_yaml,
    get_output_format,
    write_output,
)


class TestFormatOutputJson:
    def test_format_output_json_basic(self):
        developers = [
            Developer(name="Alice", can_review=True, reviewers=["Bob", "Charlie"]),
            Developer(name="Bob", can_review=True, reviewers=["Alice", "Dana"]),
        ]
        params = {
            "input": "team.csv",
            "reviewers": 2,
            "team_mode": False,
            "knowledge_mode": "anyone"
        }
        
        output = format_output_json(developers, params)
        
        data = json.loads(output)
        
        assert "generated_at" in data
        assert data["parameters"]["input"] == "team.csv"
        assert data["parameters"]["reviewers"] == 2
        assert data["parameters"]["team_mode"] is False
        assert data["parameters"]["knowledge_mode"] == "anyone"
        assert len(data["assignments"]) == 2
        assert data["assignments"][0]["developer"] == "Alice"
        assert data["assignments"][0]["reviewers"] == ["Bob", "Charlie"]
        assert data["assignments"][1]["developer"] == "Bob"
        assert data["assignments"][1]["reviewers"] == ["Alice", "Dana"]

    def test_format_output_json_with_team_mode(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", reviewers=["Bob"]),
            Developer(name="Bob", can_review=True, team="backend", reviewers=["Alice"]),
        ]
        params = {
            "input": "team.csv",
            "reviewers": 1,
            "team_mode": True,
            "knowledge_mode": "mentorship"
        }
        
        output = format_output_json(developers, params)
        
        data = json.loads(output)
        
        assert data["parameters"]["team_mode"] is True
        assert data["parameters"]["knowledge_mode"] == "mentorship"

    def test_format_output_json_with_empty_reviewers(self):
        developers = [
            Developer(name="Alice", can_review=True, reviewers=[]),
        ]
        params = {
            "input": "team.csv",
            "reviewers": 2,
            "team_mode": False,
            "knowledge_mode": "anyone"
        }
        
        output = format_output_json(developers, params)
        
        data = json.loads(output)
        
        assert data["assignments"][0]["reviewers"] == []


class TestFormatOutputYaml:
    def test_format_output_yaml_basic(self):
        developers = [
            Developer(name="Alice", can_review=True, reviewers=["Bob", "Charlie"]),
            Developer(name="Bob", can_review=True, reviewers=["Alice"]),
        ]
        params = {
            "input": "team.csv",
            "reviewers": 2,
            "team_mode": False,
            "knowledge_mode": "anyone"
        }
        
        output = format_output_yaml(developers, params)
        
        assert 'generated_at:' in output
        assert 'input: team.csv' in output
        assert 'reviewers: 2' in output
        assert 'team_mode: false' in output
        assert 'developer: Alice' in output
        assert '- Bob' in output
        assert '- Charlie' in output

    def test_format_output_yaml_with_team_mode(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", reviewers=["Bob"]),
        ]
        params = {
            "input": "team.csv",
            "reviewers": 1,
            "team_mode": True,
            "knowledge_mode": "experts-only"
        }
        
        output = format_output_yaml(developers, params)
        
        assert 'team_mode: true' in output
        assert 'knowledge_mode: experts-only' in output

    def test_format_output_yaml_with_empty_reviewers(self):
        developers = [
            Developer(name="Alice", can_review=True, reviewers=[]),
        ]
        params = {
            "input": "team.csv",
            "reviewers": 2,
            "team_mode": False,
            "knowledge_mode": "anyone"
        }
        
        output = format_output_yaml(developers, params)
        
        assert 'reviewers: []' in output


class TestGetOutputFormat:
    def test_format_from_json_extension(self):
        assert get_output_format("output.json", None) == "json"
        assert get_output_format("path/to/file.json", None) == "json"

    def test_format_from_yaml_extension(self):
        assert get_output_format("output.yaml", None) == "yaml"
        assert get_output_format("output.yml", None) == "yaml"
        assert get_output_format("path/to/file.yml", None) == "yaml"

    def test_format_from_explicit_arg(self):
        assert get_output_format(None, "json") == "json"
        assert get_output_format(None, "yaml") == "yaml"
        assert get_output_format(None, "csv") == "csv"

    def test_explicit_arg_overrides_extension(self):
        assert get_output_format("output.json", "yaml") == "yaml"
        assert get_output_format("output.yaml", "json") == "json"
        assert get_output_format("output.csv", "json") == "json"

    def test_default_format(self):
        assert get_output_format(None, None) == "csv"
        assert get_output_format("output.csv", None) == "csv"
        assert get_output_format("output.txt", None) == "csv"


class TestWriteOutput:
    def test_write_output_json(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        content = '{"test": "data"}'
        write_output(content, temp_path)
        
        with open(temp_path, 'r') as f:
            assert f.read() == '{"test": "data"}'
        
        import os
        os.unlink(temp_path)

    def test_write_output_yaml(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        content = "key: value\n"
        write_output(content, temp_path)
        
        with open(temp_path, 'r') as f:
            assert f.read() == "key: value\n"
        
        import os
        os.unlink(temp_path)
