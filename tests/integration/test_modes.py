import json
import os
import subprocess
import tempfile


class TestDryRunMode:
    """Test dry-run mode functionality."""
    
    def test_dry_run_does_not_modify_csv(self, temp_csv):
        with open(temp_csv, 'r') as f:
            original_content = f.read()
        
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--dry-run"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "[DRY RUN]" in result.stdout
        
        with open(temp_csv, 'r') as f:
            final_content = f.read()
        
        assert original_content == final_content
    
    def test_dry_run_does_not_modify_history(self, temp_csv):
        history_path = temp_csv.replace('.csv', '_history.json')
        
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--dry-run"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert not os.path.exists(history_path)
    
    def test_dry_run_output_format(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--dry-run"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "[DRY RUN]" in result.stdout
        assert "Preview" in result.stdout
        assert "Assignments:" in result.stdout
        assert "Total:" in result.stdout
    
    def test_dry_run_shows_warnings(self, temp_csv_teams):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_teams, "-r", "2", "-t", "--dry-run"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Warnings" in result.stdout or "would appear" in result.stdout
    
    def test_dry_run_short_flag(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-n"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "[DRY RUN]" in result.stdout
    
    def test_dry_run_with_knowledge_mode(self, temp_csv_full):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_full, "-r", "2", "-k", "experts-only", "--dry-run"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "[DRY RUN]" in result.stdout
    
    def test_dry_run_no_history_loaded(self, temp_csv):
        history_path = "./pairing_history.json"
        
        if os.path.exists(history_path):
            os.unlink(history_path)
        
        result1 = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        with open(history_path, 'r') as f:
            history_after_normal = json.load(f)
        
        result2 = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--dry-run"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        with open(history_path, 'r') as f:
            history_after_dry_run = json.load(f)
        
        assert history_after_normal == history_after_dry_run
        
        os.unlink(history_path)


class TestFreshMode:
    """Test fresh mode functionality."""
    
    def test_fresh_ignores_existing_history(self, temp_csv):
        history_path = "./pairing_history.json"
        
        if os.path.exists(history_path):
            os.unlink(history_path)
        
        subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        with open(history_path, 'r') as f:
            history1 = json.load(f)
        
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--fresh"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        with open(history_path, 'r') as f:
            history2 = json.load(f)
        
        assert history1 != history2
        
        if os.path.exists(history_path):
            os.unlink(history_path)
    
    def test_fresh_short_flag(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-f"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Successfully assigned" in result.stdout
    
    def test_fresh_with_team_mode(self, temp_csv_teams):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv_teams, "-r", "2", "-t", "--fresh"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
    
    def test_fresh_with_dry_run(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--fresh", "--dry-run"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "[DRY RUN]" in result.stdout


class TestVerboseQuiet:
    """Test verbose and quiet output modes."""

    def test_default_verbosity_shows_success(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Successfully assigned" in result.stdout

    def test_verbose_flag_shows_info(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-v"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Successfully assigned" in result.stdout
        assert "Output written to:" in result.stderr

    def test_verbose_flag_short(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--verbose"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Output written to:" in result.stderr

    def test_quiet_flag_suppresses_output(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-q"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_quiet_flag_short(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--quiet"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_silent_flag_suppresses_all(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-qq"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_quiet_still_shows_errors(self):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", "nonexistent.csv", "-r", "2", "-q"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert "Error:" in result.stderr

    def test_verbose_with_dry_run(self, temp_csv):
        result = subprocess.run(
            ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "--dry-run", "-v"],
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "[DRY RUN]" in result.stdout

    def test_quiet_with_warnings(self, temp_csv):
        content = """name,can_review
Alice,true
Bob,false
Charlie,true"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_path, "-r", "2", "-q"],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0
            assert result.stdout == ""
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
