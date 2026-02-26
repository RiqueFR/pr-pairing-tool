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

import logging
import sys

from .models import (
    KnowledgeMode,
    History,
    PRPairingError,
)
from .io import (
    load_developers,
    save_developers,
    load_history,
    save_history,
)
from .exclusions import (
    load_exclusions,
    parse_exclusions_cli,
)
from .pairing import assign_reviewers
from .cli import (
    parse_arguments,
    handle_error,
    print_dry_run_summary,
    print_success_summary,
)

logger = logging.getLogger(__name__)


def main():
    args = parse_arguments()
    
    developers: list = []
    try:
        developers = load_developers(args.input)
    except PRPairingError as e:
        handle_error(e)
    
    valid_developers = {dev.name for dev in developers}
    
    exclusions = set()
    
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
        except PRPairingError as e:
            handle_error(e)
    
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
    
    balance_mode = not args.no_balance if args.no_balance is not None else True
    
    warnings = assign_reviewers(
        developers=developers,
        history=history,
        num_reviewers=args.reviewers,
        team_mode=args.team_mode,
        knowledge_mode=knowledge_mode,
        exclusions=exclusions,
        balance_mode=balance_mode
    )
    
    if args.dry_run:
        print_dry_run_summary(developers, warnings)
    else:
        try:
            save_developers(args.input, developers)
        except PRPairingError as e:
            handle_error(e)
        
        save_history(args.history, history)
        
        verbosity = args.verbose - args.quiet
        print_success_summary(developers, args.history, warnings, verbosity)


if __name__ == "__main__":
    main()
