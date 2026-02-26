import json
import os
import subprocess
import tempfile


class TestHistoryPersistence:
    """Test that history is persisted across runs."""
    
    def test_history_persists_between_runs(self, temp_csv):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"pairs": {}, "last_run": None}, f)
            history_path = f.name

        try:
            result1 = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-H", history_path],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
                capture_output=True,
                text=True
            )
            
            with open(history_path, 'r') as f:
                history1 = json.load(f)
            
            assert len(history1["pairs"]) > 0
            
            result2 = subprocess.run(
                ["python", "pr_pairing.py", "-i", temp_csv, "-r", "2", "-H", history_path],
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
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
