import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .models import KnowledgeMode, PRPairingError, FileError
from .config import (
    find_config_file,
    load_config,
    merge_config,
    normalize_bool,
    DEFAULT_REVIEWERS,
)


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


def create_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser."""
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
        default=None,
        help=f"Number of reviewers per developer (default: {DEFAULT_REVIEWERS})"
    )
    parser.add_argument(
        "-H", "--history",
        default=None,
        help="Path to history file (default: ./pairing_history.json)"
    )
    parser.add_argument(
        "-t", "--team-mode",
        action="store_true",
        default=None,
        help="Enable team-based pairing (prioritize same-team reviewers)"
    )
    parser.add_argument(
        "-k", "--knowledge-mode",
        choices=[km.value for km in KnowledgeMode],
        default=None,
        help="Knowledge-based pairing mode: anyone (default), experts-only, mentorship, similar-levels"
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        default=None,
        help="Preview assignments without saving"
    )
    parser.add_argument(
        "-f", "--fresh",
        action="store_true",
        default=None,
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
        default=None,
        help="Path to exclusion file (CSV or YAML format)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=None,
        help="Increase output verbosity (-v, -vv, -vvv)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="count",
        default=None,
        help="Decrease output verbosity (-q, -qq)"
    )
    parser.add_argument(
        "-c", "--config",
        default=None,
        help="Path to config file (optional)"
    )
    parser.add_argument(
        "--no-balance",
        action="store_true",
        default=None,
        help="Disable balance mode (assign reviewers without balancing load)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        default=None,
        help="Validate input without processing"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=None,
        help="Treat warnings as errors"
    )
    return parser


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments and merge with config file."""
    parser = create_parser()
    args = parser.parse_args()
    
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
    
    return args


def handle_error(error: Exception) -> None:
    """Print error message and exit with error code."""
    logger.error(f"Error: {error}")
    sys.exit(1)


def print_dry_run_summary(developers, warnings: list[str]) -> None:
    """Print preview of assignments without saving."""
    print("\n[DRY RUN] Preview - No files will be modified")
    print("-" * 40)
    print("Assignments:")
    for dev in developers:
        reviewers = ", ".join(dev.reviewers) if dev.reviewers else "(no reviewers)"
        print(f"  {dev.name}: {reviewers}")
    print("-" * 40)
    total = len([d for d in developers if d.reviewers])
    print(f"Total: {total} developers assigned")
    
    if warnings:
        print("\nWarnings (would appear):")
        for warning in warnings:
            print(f"  - {warning}")


def print_success_summary(developers, history_path: str, warnings: list[str], verbosity: int) -> None:
    """Print success message and summary."""
    if verbosity >= 0:
        print(f"Successfully assigned reviewers to {len(developers)} developers")
        logger.info(f"Output written to: input file")
        logger.info(f"History saved to: {history_path}")
    
    if warnings:
        logger.warning("Warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")
