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
import logging
import sys

from .models import (
    Developer,
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
from .requirements import (
    load_requirements,
    parse_requirements_cli,
    check_conflicts,
)
from .pairing import assign_reviewers
from .output import (
    format_output_json,
    format_output_yaml,
    get_output_format,
    write_output,
)
from .cli import (
    parse_arguments,
    handle_error,
    print_dry_run_summary,
    print_success_summary,
)
from .validation import (
    validate_csv,
    print_validation_result,
)

logger = logging.getLogger(__name__)


def load_and_validate_input(args: argparse.Namespace) -> tuple[list[Developer], bool]:
    developers: list[Developer] = []
    try:
        developers = load_developers(args.input)
    except PRPairingError as e:
        handle_error(e)

    validation_result = validate_csv(developers)
    verbosity = args.verbose - args.quiet
    print_validation_result(validation_result, args.input, developers, verbosity)
    if verbosity >= 0:
        print()

    if args.validate:
        return [], True

    if args.strict and (not validation_result.is_valid or validation_result.warnings):
        sys.exit(1)

    return developers, False


def process_exclusions(args: argparse.Namespace, valid_developers: set[str]) -> set[tuple[str, str]]:
    exclusions: set[tuple[str, str]] = set()

    if args.exclude:
        cli_exclusions = parse_exclusions_cli(args.exclude, valid_developers)
        exclusions.update(cli_exclusions)
        if cli_exclusions:
            logger.info(f"Loaded {len(cli_exclusions)} exclusion(s)")

    if args.exclude_file:
        try:
            file_exclusions = load_exclusions(args.exclude_file, valid_developers)
            exclusions.update(file_exclusions)
            logger.info(f"Loaded {len(file_exclusions)} exclusion(s) from file: {args.exclude_file}")
        except PRPairingError as e:
            handle_error(e)

    if exclusions:
        logger.info(f"Total exclusions: {len(exclusions)}")

    return exclusions


def process_requirements(
    args: argparse.Namespace,
    valid_developers: set[str],
    exclusions: set[tuple[str, str]]
) -> dict[str, list[str]]:
    requirements: dict[str, list[str]] = {}

    if args.require:
        cli_requirements = parse_requirements_cli(args.require, valid_developers)
        for dev, revs in cli_requirements.items():
            if dev not in requirements:
                requirements[dev] = []
            requirements[dev].extend(revs)
        if cli_requirements:
            logger.info(f"Loaded {len(cli_requirements)} requirement(s)")

    if args.require_file:
        try:
            file_requirements = load_requirements(args.require_file, valid_developers)
            for dev, revs in file_requirements.items():
                if dev not in requirements:
                    requirements[dev] = []
                requirements[dev].extend(revs)
            logger.info(f"Loaded {len(file_requirements)} requirement(s) from file: {args.require_file}")
        except PRPairingError as e:
            handle_error(e)

    if requirements:
        total_req = sum(len(revs) for revs in requirements.values())
        logger.info(f"Total requirements: {total_req}")

        conflicts = check_conflicts(requirements, exclusions)
        if conflicts:
            for conflict in conflicts:
                logger.error(f"Error: {conflict}")
            handle_error(PRPairingError("Conflicting requirements and exclusions detected"))

    return requirements


def prepare_history(args: argparse.Namespace) -> History:
    if args.dry_run:
        logger.info("[DRY RUN] Running in preview mode - no files will be modified")
        return History()
    elif args.fresh:
        return History()
    else:
        return load_history(args.history)


def compute_pairing_params(args: argparse.Namespace) -> tuple[KnowledgeMode, bool]:
    knowledge_mode = KnowledgeMode(args.knowledge_mode)
    balance_mode = not args.no_balance if args.no_balance is not None else True
    return knowledge_mode, balance_mode


def save_output(
    developers: list[Developer],
    args: argparse.Namespace,
    history: History,
    warnings: list[str]
) -> None:
    output_format = get_output_format(args.output, args.output_format)

    params = {
        "input": args.input,
        "reviewers": args.reviewers,
        "team_mode": args.team_mode,
        "knowledge_mode": args.knowledge_mode if args.knowledge_mode else KnowledgeMode.ANYONE.value
    }

    if output_format == "json":
        output_content = format_output_json(developers, params)
    elif output_format == "yaml":
        output_content = format_output_yaml(developers, params)
    else:
        output_content = None

    if args.output:
        if output_content:
            write_output(output_content, args.output)
            logger.info(f"Output written to: {args.output}")
        else:
            try:
                save_developers(args.input, developers)
            except PRPairingError as e:
                handle_error(e)
            logger.info(f"Output written to: {args.input}")
    elif output_format != "csv":
        print(output_content)
        try:
            save_developers(args.input, developers)
        except PRPairingError as e:
            handle_error(e)
    else:
        try:
            save_developers(args.input, developers)
        except PRPairingError as e:
            handle_error(e)

    save_history(args.history, history)

    verbosity = args.verbose - args.quiet
    print_success_summary(developers, args.history, warnings, verbosity)


def main():
    args = parse_arguments()

    developers, should_return = load_and_validate_input(args)
    if should_return:
        return

    valid_developers = {dev.name for dev in developers}

    exclusions = process_exclusions(args, valid_developers)
    requirements = process_requirements(args, valid_developers, exclusions)
    history = prepare_history(args)

    knowledge_mode, balance_mode = compute_pairing_params(args)

    warnings = assign_reviewers(
        developers=developers,
        history=history,
        num_reviewers=args.reviewers,
        team_mode=args.team_mode,
        knowledge_mode=knowledge_mode,
        exclusions=exclusions,
        requirements=requirements,
        balance_mode=balance_mode
    )

    if args.dry_run:
        print_dry_run_summary(developers, warnings)
    else:
        save_output(developers, args, history, warnings)


if __name__ == "__main__":
    main()
