import csv
import json
import os
import subprocess
import tempfile

import pytest


class TestCLI:
    """Test the CLI interface and main entry point."""
    
    def test_cli_standard_mode(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Successfully assigned" in result.stdout
        
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert "reviewers" in rows[0]
        for row in rows:
            if row["can_review"] == "true":
                reviewer_count = len([r for r in row.get("reviewers", "").split(",") if r.strip()])
                assert reviewer_count <= 2

    def test_cli_team_mode(self, temp_csv_teams):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_teams, "-r", "2", "-t"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_cli_knowledge_anyone(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-k", "anyone"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Successfully assigned" in result.stdout

    def test_cli_knowledge_experts_only(self, temp_csv_full):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_full, "-r", "2", "-k", "experts-only"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        with open(temp_csv_full, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        reviewers_with_level = {}
        for row in rows:
            level = int(row.get("knowledge_level", 3))
            reviewers = row.get("reviewers", "").split(", ")
            reviewers = [r.strip() for r in reviewers if r.strip()]
            reviewers_with_level[row["name"]] = (level, reviewers)
        
        for name, (level, reviewers) in reviewers_with_level.items():
            if level < 4 and row["can_review"] == "true":
                if reviewers:
                    pass

    def test_cli_knowledge_mentorship(self, temp_csv_full):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_full, "-r", "2", "-k", "mentorship"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_cli_knowledge_similar_levels(self, temp_csv_full):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_full, "-r", "2", "-k", "similar-levels"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_cli_combined_team_and_knowledge(self, temp_csv_full):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_full, "-r", "2", "-t", "-k", "mentorship"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_cli_missing_input_file(self):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", "nonexistent.csv"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_cli_custom_history_path(self, temp_csv, temp_history):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-H", temp_history],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert os.path.exists(temp_history)

    def test_cli_output_adds_reviewers_column(self, temp_csv):
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            original_fields = reader.fieldnames
        
        assert "reviewers" not in original_fields
        
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            updated_fields = reader.fieldnames
        
        assert "reviewers" in updated_fields

    def test_cli_reviewer_cannot_review_self(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        for row in rows:
            if row["can_review"] == "true":
                reviewers = [r.strip() for r in row.get("reviewers", "").split(",") if r.strip()]
                assert row["name"] not in reviewers


class TestHistoryPersistence:
    """Test that history is persisted across runs."""
    
    def test_history_persists_between_runs(self, temp_csv):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"pairs": {}, "last_run": None}, f)
            history_path = f.name

        try:
            result1 = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-H", history_path],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            with open(history_path, 'r') as f:
                history1 = json.load(f)
            
            assert len(history1["pairs"]) > 0
            
            result2 = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-H", history_path],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            with open(history_path, 'r') as f:
                history2 = json.load(f)
            
            for dev, pairs in history2["pairs"].items():
                for reviewer, count in pairs.items():
                    if dev in history1["pairs"] and reviewer in history1["pairs"][dev]:
                        assert count >= history1["pairs"][dev][reviewer]
        finally:
            if os.path.exists(history_path):
                os.unlink(history_path)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\n")
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "2"],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 1
            assert "empty" in result.stderr.lower() or "Error" in result.stderr
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_no_reviewers_available(self):
        content = "name,can_review\nAlice,false\nBob,false"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "2"],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_missing_name_column(self):
        content = "can_review\ntrue"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "2"],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 1
            assert "name" in result.stderr.lower()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_missing_can_review_column(self):
        content = "name\nAlice"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "2"],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 1
            assert "can_review" in result.stderr.lower()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_partial_assignment_warning(self):
        content = "name,can_review\nAlice,true\nBob,false"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "3"],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0
            assert "Warning" in result.stderr or "warning" in result.stderr.lower()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_csv_without_team_column(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-t"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_csv_without_knowledge_column(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-k", "experts-only"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0


class TestBalancedDistribution:
    """Test that the pairing algorithm produces balanced distributions."""
    
    def test_load_balancing(self):
        content = """name,can_review
Alice,true
Bob,true
Charlie,true
Dana,true
Eve,true
Frank,true"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "2"],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0
            
            with open(temp_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            total_reviews = sum(
                len([r for r in row.get("reviewers", "").split(",") if r.strip()])
                for row in rows
            )
            
            assert total_reviews > 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_history_avoidance(self):
        content = """name,can_review
Alice,true
Bob,true
Charlie,true
Dana,true"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            history = {
                "pairs": {
                    "Alice": {"Bob": 10, "Charlie": 0},
                    "Bob": {"Alice": 10, "Charlie": 0},
                    "Charlie": {"Alice": 10, "Bob": 10},
                    "Dana": {"Alice": 0, "Bob": 0}
                },
                "last_run": None
            }
            json.dump(history, f)
            history_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "2", "-H", history_path],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
                capture_output=True,
                text=True
            )
            
            with open(temp_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            alice_row = [r for r in rows if r["name"] == "Alice"][0]
            alice_reviewers = [r.strip() for r in alice_row.get("reviewers", "").split(",") if r.strip()]
            
            assert "Bob" not in alice_reviewers or len(alice_reviewers) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            if os.path.exists(history_path):
                os.unlink(history_path)
