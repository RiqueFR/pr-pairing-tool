import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import History, FileError, Developer, DEFAULT_KNOWLEDGE_LEVEL, CSVValidationError
from .config import normalize_bool


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


def parse_knowledge_level(value: Any) -> int:
    """Parse knowledge level, defaulting to 3 if invalid."""
    if not value:
        return DEFAULT_KNOWLEDGE_LEVEL
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return DEFAULT_KNOWLEDGE_LEVEL


def row_to_developer(row: dict) -> Developer:
    """Convert CSV row to Developer object."""
    if "name" not in row:
        raise CSVValidationError("CSV row missing 'name' column")
    
    name = row["name"]
    can_review = normalize_bool(row.get("can_review", "false"))
    team = row.get("team", "").strip()
    knowledge_level = parse_knowledge_level(row.get("knowledge_level"))
    
    # Extract reviewers if present
    reviewers_str = row.get("reviewers", "")
    reviewers = [r.strip() for r in reviewers_str.split(",") if r.strip()]
    
    # Store everything else in metadata
    standard_keys = {"name", "can_review", "team", "knowledge_level", "reviewers"}
    metadata = {k: v for k, v in row.items() if k not in standard_keys}
    
    return Developer(
        name=name,
        can_review=can_review,
        team=team,
        knowledge_level=knowledge_level,
        reviewers=reviewers,
        metadata=metadata
    )


def load_developers(filepath: str) -> list[Developer]:
    """Load developers from CSV file."""
    rows = load_csv(filepath)
    if not rows:
        raise CSVValidationError("Input CSV is empty")
    
    # Validate required columns
    if "name" not in rows[0]:
        raise CSVValidationError("CSV must have a 'name' column")
    if "can_review" not in rows[0]:
        raise CSVValidationError("CSV must have a 'can_review' column")
    
    return [row_to_developer(row) for row in rows]


def save_developers(filepath: str, developers: list[Developer]) -> None:
    """Save developers back to CSV, preserving original columns via metadata."""
    if not developers:
        return
        
    dicts = [d.to_dict() for d in developers]
    # Use keys from first dict as fieldnames to ensure all columns are included
    fieldnames = list(dicts[0].keys())
    save_csv(filepath, dicts, fieldnames)


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
