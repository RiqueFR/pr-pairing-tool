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
from .pairing import (
    get_knowledge_level,
    get_team,
    to_developer,
    is_same_team,
    is_expert,
    is_novice,
    get_knowledge_filter,
    get_pair_count,
    get_total_reviews_assigned,
    update_history,
    generate_team_warnings,
    build_sort_key,
    select_reviewers,
    validate_csv,
    assign_reviewers,
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
