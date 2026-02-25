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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import (
    KnowledgeMode,
    Developer,
    History,
    ReviewerCandidate,
    PRPairingError,
    CSVValidationError,
    FileError,
    DEFAULT_KNOWLEDGE_LEVEL,
    EXPERT_MIN_LEVEL,
    NOVICE_MAX_LEVEL,
)
from .config import (
    parse_args,
    CONFIG_SEARCH_PATHS,
    get_home_config_paths,
    find_config_file,
    load_config,
    merge_config,
    normalize_bool,
    DEFAULT_REVIEWERS,
)
from .io import (
    load_csv,
    save_csv,
    load_history,
    save_history,
)
from .exclusions import (
    parse_exclusion_string,
    load_exclusions_from_csv,
    load_exclusions_from_yaml,
    load_exclusions,
    parse_exclusions_cli,
)

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
    
    config_file = find_config_file(args.config)
    config = {}
    if config_file:
        try:
            config = load_config(config_file)
            logger.info(f"Loaded config from: {config_file}")
        except PRPairingError:
            handle_error(sys.exc_info()[1])
    elif args.config:
        logger.warning(f"Config file not found: {args.config}")
    
    args = merge_config(config, args)
    
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
