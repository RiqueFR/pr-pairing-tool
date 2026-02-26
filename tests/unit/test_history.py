import json
import tempfile

import pytest

from pr_pairing import (
    load_history,
    save_history,
    get_pair_count,
    get_total_reviews_assigned,
    update_history,
    History,
)


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
