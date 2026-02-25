#!/usr/bin/env python3
"""
Pull Request Pairing Tool

Assigns reviewers to developers for PR reviews with balanced distribution
and optional team-based pairing.

Usage:
    python pr_pairing.py -i team.csv -r 2
    python pr_pairing.py -i team.csv -r 2 --team-mode
    python pr_pairing.py -i team.csv -r 2 -k experts-only
    python pr_pairing.py -i team.csv -r 2 -t -k mentorship

Input CSV format:
    name,can_review,team,knowledge_level
    Alice,true,frontend,5
    Bob,true,backend,3
"""

import argparse
import csv
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, TypedDict, Union

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


def setup_logging(verbosity: int) -> None:
    """Setup logging based on verbosity level.
    
    Maps effective verbosity to logging levels:
      2: DEBUG   (-vvv) - All internal state, algorithm details
      1: INFO    (-v)   - Assignment details, candidate info  
      0: WARNING (none)  - Success message + warnings (default)
     -1: ERROR   (-q)   - Only errors
     -2: CRITICAL (-qq) - Only critical (errors + above)
    """
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    elif verbosity == 0:
        level = logging.WARNING
    elif verbosity == -1:
        level = logging.ERROR
    else:
        level = logging.CRITICAL
    
    logging.basicConfig(
        level=level,
        format='%(message)s',
        stream=sys.stderr
    )


DEFAULT_REVIEWERS = 2
DEFAULT_KNOWLEDGE_LEVEL = 3
EXPERT_MIN_LEVEL = 4
NOVICE_MAX_LEVEL = 2


class KnowledgeMode(Enum):
    ANYONE = "anyone"
    EXPERTS_ONLY = "experts-only"
    MENTORSHIP = "mentorship"
    SIMILAR_LEVELS = "similar-levels"


@dataclass
class Developer:
    name: str
    can_review: bool
    team: str = ""
    knowledge_level: int = DEFAULT_KNOWLEDGE_LEVEL
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class History:
    pairs: dict[str, dict[str, int]] = field(default_factory=dict)
    last_run: Optional[str] = None
    
    @staticmethod
    def from_dict(data: dict) -> "History":
        return History(
            pairs=data.get("pairs", {}),
            last_run=data.get("last_run")
        )
    
    def to_dict(self) -> dict:
        return {
            "pairs": self.pairs,
            "last_run": self.last_run
        }


class ReviewerCandidate(TypedDict):
    name: str
    team: str
    knowledge_level: int


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
        choices=[km.value for km in KnowledgeMode],
        default=KnowledgeMode.ANYONE.value,
        help="Knowledge-based pairing mode: anyone (default), experts-only, mentorship, similar-levels"
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Preview assignments without saving"
    )
    parser.add_argument(
        "-f", "--fresh",
        action="store_true",
        help="Ignore existing history and start fresh"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude a pair from pairing (format: DEV1:DEV2). Can be repeated."
    )
    parser.add_argument(
        "--exclude-file",
        help="Path to exclusion file (CSV or YAML format)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (-v, -vv, -vvv)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="count",
        default=0,
        help="Decrease output verbosity (-q, -qq)"
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


def save_csv(filepath: str, rows: list[dict], fieldnames: list[str]) -> None:
    """Save rows to CSV file."""
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        raise FileError(f"Error writing output file: {e}")


def parse_exclusion_string(exclusion: str, valid_developers: set[str]) -> tuple[str, str] | None:
    """Parse exclusion string in format DEV1:DEV2."""
    try:
        dev, reviewer = exclusion.split(":")
        dev = dev.strip()
        reviewer = reviewer.strip()
        if not dev or not reviewer:
            return None
        if dev not in valid_developers:
            return None
        if reviewer not in valid_developers:
            return None
        return (dev, reviewer)
    except ValueError:
        return None


def load_exclusions_from_csv(filepath: str) -> set[tuple[str, str]]:
    """Load exclusion pairs from CSV file."""
    exclusions = set()
    try:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dev = row.get("developer", "").strip()
                reviewer = row.get("excluded_reviewer", "").strip()
                if dev and reviewer:
                    exclusions.add((dev, reviewer))
    except FileNotFoundError:
        raise FileError(f"Exclusion file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading exclusion file: {e}")
    return exclusions


def load_exclusions_from_yaml(filepath: str) -> set[tuple[str, str]]:
    """Load exclusion pairs from YAML file."""
    if not YAML_AVAILABLE:
        raise FileError("YAML support requires PyYAML. Install with: pip install pyyaml")
    
    exclusions = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data:
            return exclusions
        
        exclusions_list = data.get("exclusions", [])
        for item in exclusions_list:
            developers = item.get("developers", [])
            if len(developers) == 2:
                exclusions.add((developers[0], developers[1]))
                exclusions.add((developers[1], developers[0]))
    except FileNotFoundError:
        raise FileError(f"Exclusion file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading exclusion file: {e}")
    return exclusions


def load_exclusions(filepath: str, valid_developers: set[str]) -> set[tuple[str, str]]:
    """Load exclusion pairs from file (auto-detect format by extension)."""
    path = Path(filepath)
    suffix = path.suffix.lower()
    
    if suffix in (".yaml", ".yml"):
        return load_exclusions_from_yaml(filepath)
    elif suffix == ".csv":
        return load_exclusions_from_csv(filepath)
    else:
        raise FileError(f"Unsupported exclusion file format: {suffix}. Use .csv or .yaml")


def parse_exclusions_cli(exclusions: list[str], valid_developers: set[str]) -> set[tuple[str, str]]:
    """Parse exclusion list from CLI arguments."""
    result = set()
    for exc in exclusions:
        parsed = parse_exclusion_string(exc, valid_developers)
        if parsed:
            result.add(parsed)
    return result


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


def to_developer(row: dict) -> Developer:
    """Convert a row dict to a Developer object."""
    return Developer(
        name=row["name"],
        can_review=normalize_bool(row.get("can_review", "false")),
        team=get_team(row),
        knowledge_level=get_knowledge_level(row)
    )


def is_same_team(candidate: ReviewerCandidate, dev_team: str) -> bool:
    """Check if candidate is on the same team as the developer."""
    return bool(dev_team and candidate.get("team") == dev_team)


def is_expert(candidate: ReviewerCandidate) -> bool:
    """Check if candidate is an expert (level >= 4)."""
    return candidate.get("knowledge_level", DEFAULT_KNOWLEDGE_LEVEL) >= EXPERT_MIN_LEVEL


def is_novice(developer_level: int) -> bool:
    """Check if developer is a novice (level <= 2)."""
    return developer_level <= NOVICE_MAX_LEVEL


def get_knowledge_filter(knowledge_mode: KnowledgeMode, dev_knowledge: int) -> callable:
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
        KnowledgeMode.EXPERTS_ONLY: experts_only_filter,
        KnowledgeMode.MENTORSHIP: mentorship_filter,
        KnowledgeMode.SIMILAR_LEVELS: similar_levels_filter,
    }
    
    return filters.get(knowledge_mode, lambda c: True)


def get_pair_count(history: History, dev: str, reviewer: str) -> int:
    """Get how many times a reviewer has been paired with a developer."""
    return history.pairs.get(dev, {}).get(reviewer, 0)


def get_total_reviews_assigned(history: History, reviewer: str) -> int:
    """Get total number of reviews assigned to a reviewer."""
    return sum(
        dev_pairs.get(reviewer, 0)
        for dev_pairs in history.pairs.values()
    )


def update_history(history: History, dev: str, reviewers: list[str]) -> None:
    """Update history with new pairings."""
    if dev not in history.pairs:
        history.pairs[dev] = {}
    
    for reviewer in reviewers:
        history.pairs[dev][reviewer] = history.pairs[dev].get(reviewer, 0) + 1


def generate_team_warnings(
    developer: str,
    sorted_candidates: list[ReviewerCandidate],
    num_reviewers: int,
    dev_team: str
) -> list[str]:
    """Generate warnings related to team mode."""
    warnings = []
    
    same_team_count = sum(
        1 for c in sorted_candidates[:num_reviewers]
        if is_same_team(c, dev_team)
    )
    available_same_team = sum(
        1 for c in sorted_candidates
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
    
    return warnings


def build_sort_key(
    history: History,
    developer: str,
    current_assignments: dict[str, int],
    team_mode: bool,
    dev_team: Optional[str],
    knowledge_mode: KnowledgeMode,
    dev_knowledge: int
) -> callable:
    """Build a sort key function for ranking candidates."""
    def sort_key(candidate: ReviewerCandidate) -> tuple:
        name = candidate["name"]
        pair_count = get_pair_count(history, developer, name)
        total_reviews = get_total_reviews_assigned(history, name) + current_assignments.get(name, 0)
        
        team_factor = 0
        if team_mode and dev_team:
            team_factor = 0 if is_same_team(candidate, dev_team) else 1
        
        knowledge_factor = 0
        if knowledge_mode not in (KnowledgeMode.ANYONE, KnowledgeMode.EXPERTS_ONLY):
            reviewer_knowledge = candidate.get("knowledge_level", DEFAULT_KNOWLEDGE_LEVEL)
            if knowledge_mode == KnowledgeMode.MENTORSHIP:
                knowledge_factor = -reviewer_knowledge if is_novice(dev_knowledge) else 0
            elif knowledge_mode == KnowledgeMode.SIMILAR_LEVELS:
                knowledge_factor = abs(reviewer_knowledge - dev_knowledge)
        
        return (team_factor, knowledge_factor, pair_count, total_reviews)
    
    return sort_key


def select_reviewers(
    developer: str,
    candidates: list[ReviewerCandidate],
    history: History,
    num_reviewers: int,
    team_mode: bool,
    dev_team: Optional[str],
    current_assignments: dict[str, int],
    knowledge_mode: KnowledgeMode = KnowledgeMode.ANYONE,
    dev_knowledge: int = DEFAULT_KNOWLEDGE_LEVEL,
    exclusions: set[tuple[str, str]] = None
) -> tuple[list[str], list[str]]:
    """
    Select reviewers for a developer.
    Returns (selected_reviewers, warnings).
    """
    warnings = []
    
    if exclusions is None:
        exclusions = set()
    
    candidates = [c for c in candidates if c["name"] != developer]
    
    if not candidates:
        return [], [f"No reviewers available for {developer}"]
    
    excluded_reviewers = {reviewer for dev, reviewer in exclusions if dev == developer}
    if excluded_reviewers:
        candidates = [c for c in candidates if c["name"] not in excluded_reviewers]
        
        if not candidates:
            warnings.append(
                f"{developer}: All reviewers excluded, cannot assign any reviewers"
            )
            return [], warnings
    
    if knowledge_mode != KnowledgeMode.ANYONE:
        filter_fn = get_knowledge_filter(knowledge_mode, dev_knowledge)
        filtered_candidates = [c for c in candidates if filter_fn(c)]
        
        if not filtered_candidates:
            if knowledge_mode == KnowledgeMode.EXPERTS_ONLY:
                warnings.append(f"{developer}: No experts (level {EXPERT_MIN_LEVEL}-5) available for review")
            elif knowledge_mode == KnowledgeMode.MENTORSHIP:
                warnings.append(f"{developer}: No mentors (level {EXPERT_MIN_LEVEL}-5) available for novice developer")
            else:
                warnings.append(f"{developer}: No suitable reviewers found")
            return [], warnings
        
        candidates = filtered_candidates
    
    sort_key_fn = build_sort_key(
        history, developer, current_assignments,
        team_mode, dev_team, knowledge_mode, dev_knowledge
    )
    sorted_candidates = sorted(candidates, key=sort_key_fn)
    selected = [c["name"] for c in sorted_candidates[:num_reviewers]]
    
    if team_mode and dev_team:
        warnings.extend(generate_team_warnings(developer, sorted_candidates, num_reviewers, dev_team))
    
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
    knowledge_mode: KnowledgeMode = KnowledgeMode.ANYONE,
    exclusions: set[tuple[str, str]] = None
) -> tuple[list[dict], list[str]]:
    """
    Assign reviewers to all developers.
    Returns (updated_rows, warnings).
    """
    all_warnings = []
    
    if exclusions is None:
        exclusions = set()
    
    developers = [to_developer(row) for row in rows]
    reviewers = [d for d in developers if d.can_review]
    
    reviewers_list: list[ReviewerCandidate] = [
        {"name": d.name, "team": d.team, "knowledge_level": d.knowledge_level}
        for d in reviewers
    ]
    
    current_assignments = defaultdict(int)
    
    updated_rows = []
    for idx, developer in enumerate(developers):
        original_row = rows[idx]
        
        if not reviewers_list:
            new_row = dict(original_row)
            new_row["reviewers"] = ""
            all_warnings.append("No reviewers available in the team")
            updated_rows.append(new_row)
            continue
        
        selected, warnings = select_reviewers(
            developer=developer.name,
            candidates=reviewers_list,
            history=history,
            num_reviewers=num_reviewers,
            team_mode=team_mode,
            dev_team=developer.team if developer.team else None,
            current_assignments=current_assignments,
            knowledge_mode=knowledge_mode,
            dev_knowledge=developer.knowledge_level,
            exclusions=exclusions
        )
        
        all_warnings.extend(warnings)
        
        for reviewer in selected:
            current_assignments[reviewer] += 1
        
        update_history(history, developer.name, selected)
        
        new_row = dict(original_row)
        new_row["reviewers"] = ", ".join(selected)
        
        if len(selected) < num_reviewers and selected:
            all_warnings.append(
                f"{developer.name}: Only assigned {len(selected)}/{num_reviewers} reviewers (not enough available)"
            )
        
        updated_rows.append(new_row)
    
    return updated_rows, all_warnings


def print_dry_run_summary(updated_rows: list[dict], warnings: list[str]) -> None:
    """Print preview of assignments without saving."""
    print("\n[DRY RUN] Preview - No files will be modified")
    print("-" * 40)
    print("Assignments:")
    for row in updated_rows:
        name = row.get("name", "Unknown")
        reviewers = row.get("reviewers", "")
        print(f"  {name}: {reviewers if reviewers else '(no reviewers)'}")
    print("-" * 40)
    total = len([r for r in updated_rows if r.get("reviewers")])
    print(f"Total: {total} developers assigned")
    
    if warnings:
        print("\nWarnings (would appear):")
        for warning in warnings:
            print(f"  - {warning}")


def handle_error(error: Exception) -> None:
    """Print error message and exit with error code."""
    logger.error(f"Error: {error}")
    sys.exit(1)


def main():
    args = parse_args()
    
    verbosity = args.verbose - args.quiet
    setup_logging(verbosity)
    
    try:
        rows = load_csv(args.input)
        validate_csv(rows)
    except PRPairingError:
        handle_error(sys.exc_info()[1])
    
    valid_developers = {row["name"] for row in rows}
    
    exclusions: set[tuple[str, str]] = set()
    
    if args.exclude:
        cli_exclusions = parse_exclusions_cli(args.exclude, valid_developers)
        exclusions.update(cli_exclusions)
        if cli_exclusions:
            logger.info(f"Loaded {len(cli_exclusions)} exclusion(s) from CLI arguments")
    
    if args.exclude_file:
        try:
            file_exclusions = load_exclusions(args.exclude_file, valid_developers)
            exclusions.update(file_exclusions)
            logger.info(f"Loaded {len(file_exclusions)} exclusion(s) from file: {args.exclude_file}")
        except PRPairingError:
            handle_error(sys.exc_info()[1])
    
    if exclusions:
        logger.info(f"Total exclusions: {len(exclusions)}")
    
    if args.dry_run:
        logger.info("[DRY RUN] Running in preview mode - no files will be modified")
        history = History()
    elif args.fresh:
        history = History()
    else:
        history = load_history(args.history)
    
    knowledge_mode = KnowledgeMode(args.knowledge_mode)
    
    updated_rows, warnings = assign_reviewers(
        rows=rows,
        history=history,
        num_reviewers=args.reviewers,
        team_mode=args.team_mode,
        knowledge_mode=knowledge_mode,
        exclusions=exclusions
    )
    
    if args.dry_run:
        print_dry_run_summary(updated_rows, warnings)
    else:
        fieldnames = list(rows[0].keys())
        if "reviewers" not in fieldnames:
            fieldnames.append("reviewers")
        
        try:
            save_csv(args.input, updated_rows, fieldnames)
        except PRPairingError:
            handle_error(sys.exc_info()[1])
        
        save_history(args.history, history)
        
        verbosity = args.verbose - args.quiet
        if verbosity >= 0:
            print(f"Successfully assigned reviewers to {len(updated_rows)} developers")
            logger.info(f"Output written to: {args.input}")
            logger.info(f"History saved to: {args.history}")
        
        if warnings:
            logger.warning("Warnings:")
            for warning in warnings:
                logger.warning(f"  - {warning}")


if __name__ == "__main__":
    main()
