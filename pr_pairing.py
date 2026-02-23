#!/usr/bin/env python3
"""
Pull Request Pairing Tool

Assigns reviewers to developers for PR reviews with balanced distribution
and optional team-based pairing.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_REVIEWERS = 2
DEFAULT_KNOWLEDGE_LEVEL = 3
EXPERT_MIN_LEVEL = 4
NOVICE_MAX_LEVEL = 2
HISTORY_DEFAULT = {"pairs": {}, "last_run": None}


@dataclass
class Developer:
    name: str
    can_review: bool
    team: str = ""
    knowledge_level: int = DEFAULT_KNOWLEDGE_LEVEL


History = dict[str, dict[str, int]]
ReviewerCandidate = dict


class PRPairingError(Exception):
    """Base exception for PR pairing tool."""
    pass


class CSVValidationError(PRPairingError):
    """CSV validation failed."""
    pass


class FileError(PRPairingError):
    """File operation failed."""
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Assign PR reviewers to developers with balanced distribution"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to input CSV file"
    )
    parser.add_argument(
        "-r", "--reviewers",
        type=int,
        default=DEFAULT_REVIEWERS,
        help=f"Number of reviewers per developer (default: {DEFAULT_REVIEWERS})"
    )
    parser.add_argument(
        "-H", "--history",
        default="./pairing_history.json",
        help="Path to history file (default: ./pairing_history.json)"
    )
    parser.add_argument(
        "-t", "--team-mode",
        action="store_true",
        help="Enable team-based pairing (prioritize same-team reviewers)"
    )
    parser.add_argument(
        "-k", "--knowledge-mode",
        choices=["anyone", "experts-only", "mentorship", "similar-levels"],
        default="anyone",
        help="Knowledge-based pairing mode: anyone (default), experts-only, mentorship, similar-levels"
    )
    return parser.parse_args()


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


def load_history(filepath: str) -> History:
    """Load pairing history from JSON file."""
    path = Path(filepath)
    if not path.exists():
        return HISTORY_DEFAULT.copy()
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        return HISTORY_DEFAULT.copy()


def save_history(filepath: str, history: History) -> None:
    """Save pairing history to JSON file."""
    history["last_run"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        raise FileError(f"Error writing history file: {e}")


def save_csv(filepath: str, rows: list[dict], fieldnames: list[str]) -> None:
    """Save rows to CSV file."""
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        raise FileError(f"Error writing output file: {e}")


def normalize_bool(value: str) -> bool:
    """Convert string to boolean."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def get_knowledge_level(row: dict) -> int:
    """Extract knowledge level from row, defaulting to 3 if not present or invalid."""
    level = row.get("knowledge_level", "").strip()
    if level:
        try:
            return int(level)
        except ValueError:
            return DEFAULT_KNOWLEDGE_LEVEL
    return DEFAULT_KNOWLEDGE_LEVEL


def get_team(row: dict) -> str:
    """Extract team from row, defaulting to empty string."""
    team = row.get("team", "")
    return team.strip() if team else ""


def is_same_team(candidate: ReviewerCandidate, dev_team: str) -> bool:
    """Check if candidate is on the same team as the developer."""
    return bool(dev_team and candidate.get("team") == dev_team)


def is_expert(candidate: ReviewerCandidate) -> bool:
    """Check if candidate is an expert (level >= 4)."""
    return candidate.get("knowledge_level", DEFAULT_KNOWLEDGE_LEVEL) >= EXPERT_MIN_LEVEL


def is_novice(developer_level: int) -> bool:
    """Check if developer is a novice (level <= 2)."""
    return developer_level <= NOVICE_MAX_LEVEL


def knowledge_filter(knowledge_mode: str, dev_knowledge: int) -> callable:
    """Return a filter function based on knowledge mode."""
    
    def experts_only_filter(candidate: ReviewerCandidate) -> bool:
        return is_expert(candidate)
    
    def mentorship_filter(candidate: ReviewerCandidate) -> bool:
        if is_novice(dev_knowledge):
            return is_expert(candidate)
        return True
    
    def similar_levels_filter(candidate: ReviewerCandidate) -> bool:
        return True
    
    filters = {
        "experts-only": experts_only_filter,
        "mentorship": mentorship_filter,
        "similar-levels": similar_levels_filter,
    }
    
    return filters.get(knowledge_mode, lambda c: True)


def get_pair_count(history: History, dev: str, reviewer: str) -> int:
    """Get how many times a reviewer has been paired with a developer."""
    return history.get("pairs", {}).get(dev, {}).get(reviewer, 0)


def get_total_reviews_assigned(history: History, reviewer: str) -> int:
    """Get total number of reviews assigned to a reviewer."""
    return sum(
        dev_pairs.get(reviewer, 0)
        for dev_pairs in history.get("pairs", {}).values()
    )


def update_history(history: History, dev: str, reviewers: list[str]) -> None:
    """Update history with new pairings."""
    if "pairs" not in history:
        history["pairs"] = {}
    
    if dev not in history["pairs"]:
        history["pairs"][dev] = {}
    
    for reviewer in reviewers:
        history["pairs"][dev][reviewer] = history["pairs"][dev].get(reviewer, 0) + 1


def select_reviewers(
    developer: str,
    candidates: list[ReviewerCandidate],
    history: History,
    num_reviewers: int,
    team_mode: bool,
    dev_team: Optional[str],
    current_assignments: dict[str, int],
    knowledge_mode: str = "anyone",
    dev_knowledge: int = DEFAULT_KNOWLEDGE_LEVEL
) -> tuple[list[str], list[str]]:
    """
    Select reviewers for a developer.
    Returns (selected_reviewers, warnings).
    """
    warnings = []
    
    candidates = [c for c in candidates if c["name"] != developer]
    
    if not candidates:
        return [], [f"No reviewers available for {developer}"]
    
    if knowledge_mode != "anyone":
        filter_fn = knowledge_filter(knowledge_mode, dev_knowledge)
        filtered_candidates = [c for c in candidates if filter_fn(c)]
        
        if not filtered_candidates:
            if knowledge_mode == "experts-only":
                warnings.append(f"{developer}: No experts (level {EXPERT_MIN_LEVEL}-5) available for review")
            elif knowledge_mode == "mentorship":
                warnings.append(f"{developer}: No mentors (level {EXPERT_MIN_LEVEL}-5) available for novice developer")
            else:
                warnings.append(f"{developer}: No suitable reviewers found")
            return [], warnings
        
        candidates = filtered_candidates
    
    def sort_key(candidate: ReviewerCandidate) -> tuple:
        name = candidate["name"]
        pair_count = get_pair_count(history, developer, name)
        total_reviews = get_total_reviews_assigned(history, name) + current_assignments.get(name, 0)
        
        team_factor = 0
        if team_mode and dev_team:
            team_factor = 0 if is_same_team(candidate, dev_team) else 1
        
        knowledge_factor = 0
        if knowledge_mode not in ("anyone", "experts-only"):
            reviewer_knowledge = candidate.get("knowledge_level", DEFAULT_KNOWLEDGE_LEVEL)
            if knowledge_mode == "mentorship":
                knowledge_factor = -reviewer_knowledge if is_novice(dev_knowledge) else 0
            elif knowledge_mode == "similar-levels":
                knowledge_factor = abs(reviewer_knowledge - dev_knowledge)
        
        return (team_factor, knowledge_factor, pair_count, total_reviews)
    
    sorted_candidates = sorted(candidates, key=sort_key)
    selected = [c["name"] for c in sorted_candidates[:num_reviewers]]
    
    if team_mode and dev_team:
        same_team_count = sum(
            1 for c in sorted_candidates[:num_reviewers]
            if is_same_team(c, dev_team)
        )
        available_same_team = sum(
            1 for c in candidates
            if is_same_team(c, dev_team)
        )
        
        if same_team_count < num_reviewers and available_same_team > 0:
            warnings.append(
                f"{developer}: Only {same_team_count}/{num_reviewers} reviewers from same team"
            )
        elif available_same_team == 0 and num_reviewers > 0:
            warnings.append(
                f"{developer}: No reviewers available in team '{dev_team}', used other teams"
            )
    
    return selected, warnings


def validate_csv(rows: list[dict]) -> None:
    """Validate CSV has required columns."""
    if not rows:
        raise CSVValidationError("Input CSV is empty")
    if "name" not in rows[0]:
        raise CSVValidationError("CSV must have a 'name' column")
    if "can_review" not in rows[0]:
        raise CSVValidationError("CSV must have a 'can_review' column")


def assign_reviewers(
    rows: list[dict],
    history: History,
    num_reviewers: int,
    team_mode: bool,
    knowledge_mode: str = "anyone"
) -> tuple[list[dict], list[str]]:
    """
    Assign reviewers to all developers.
    Returns (updated_rows, warnings).
    """
    all_warnings = []
    
    reviewers_list = [
        {
            "name": row["name"],
            "team": get_team(row),
            "knowledge_level": get_knowledge_level(row)
        }
        for row in rows
        if normalize_bool(row.get("can_review", "false"))
    ]
    
    current_assignments = defaultdict(int)
    
    updated_rows = []
    for row in rows:
        new_row = dict(row)
        dev_name = row["name"]
        dev_team = get_team(row)
        dev_knowledge = get_knowledge_level(row)
        
        if not reviewers_list:
            new_row["reviewers"] = ""
            all_warnings.append("No reviewers available in the team")
            updated_rows.append(new_row)
            continue
        
        selected, warnings = select_reviewers(
            developer=dev_name,
            candidates=reviewers_list,
            history=history,
            num_reviewers=num_reviewers,
            team_mode=team_mode,
            dev_team=dev_team if dev_team else None,
            current_assignments=current_assignments,
            knowledge_mode=knowledge_mode,
            dev_knowledge=dev_knowledge
        )
        
        all_warnings.extend(warnings)
        
        for reviewer in selected:
            current_assignments[reviewer] += 1
        
        update_history(history, dev_name, selected)
        
        new_row["reviewers"] = ", ".join(selected)
        
        if len(selected) < num_reviewers and selected:
            all_warnings.append(
                f"{dev_name}: Only assigned {len(selected)}/{num_reviewers} reviewers (not enough available)"
            )
        
        updated_rows.append(new_row)
    
    return updated_rows, all_warnings


def main():
    args = parse_args()
    
    try:
        rows = load_csv(args.input)
        validate_csv(rows)
    except FileError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except CSVValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    history = load_history(args.history)
    
    updated_rows, warnings = assign_reviewers(
        rows=rows,
        history=history,
        num_reviewers=args.reviewers,
        team_mode=args.team_mode,
        knowledge_mode=args.knowledge_mode
    )
    
    fieldnames = list(rows[0].keys())
    if "reviewers" not in fieldnames:
        fieldnames.append("reviewers")
    
    try:
        save_csv(args.input, updated_rows, fieldnames)
    except FileError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    save_history(args.history, history)
    
    print(f"Successfully assigned reviewers to {len(updated_rows)} developers")
    print(f"Output written to: {args.input}")
    print(f"History saved to: {args.history}")
    
    if warnings:
        print("\nWarnings:", file=sys.stderr)
        for warning in warnings:
            print(f"  - {warning}", file=sys.stderr)


if __name__ == "__main__":
    main()
