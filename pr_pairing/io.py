import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .models import History, FileError


def load_csv(filepath: str) -> list[dict]:
    """Load CSV file and return list of rows as dictionaries."""
    try:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except FileNotFoundError:
        raise FileError(f"Input file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading input file: {e}")


def save_csv(filepath: str, rows: list[dict], fieldnames: list[str]) -> None:
    """Save rows to CSV file."""
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        raise FileError(f"Error writing output file: {e}")


def load_history(filepath: str) -> History:
    """Load pairing history from JSON file."""
    path = Path(filepath)
    if not path.exists():
        return History()
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return History.from_dict(data)
    except json.JSONDecodeError:
        return History()


def save_history(filepath: str, history: History) -> None:
    """Save pairing history to JSON file."""
    history.last_run = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history.to_dict(), f, indent=2)
    except Exception as e:
        raise FileError(f"Error writing history file: {e}")
