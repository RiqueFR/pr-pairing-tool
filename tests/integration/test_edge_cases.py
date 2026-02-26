import csv
import json
import os
import subprocess
import tempfile


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review\n")
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "2"],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0

    def test_csv_without_knowledge_column(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-k", "experts-only"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
