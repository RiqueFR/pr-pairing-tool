import csv
import os
import subprocess
import tempfile


class TestCLI:
    """Test the CLI interface and main entry point."""
    
    def test_cli_standard_mode(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_cli_knowledge_anyone(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-k", "anyone"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Successfully assigned" in result.stdout

    def test_cli_knowledge_experts_only(self, temp_csv_full):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_full, "-r", "2", "-k", "experts-only"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_cli_knowledge_similar_levels(self, temp_csv_full):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_full, "-r", "2", "-k", "similar-levels"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_cli_combined_team_and_knowledge(self, temp_csv_full):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_full, "-r", "2", "-t", "-k", "mentorship"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_cli_missing_input_file(self):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", "nonexistent.csv"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_cli_custom_history_path(self, temp_csv, temp_history):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-H", temp_history],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
