import argparse
from pathlib import Path
from typing import Optional

from .models import KnowledgeMode, FileError


DEFAULT_REVIEWERS = 2


CONFIG_SEARCH_PATHS = [
    ".prpairingrc",
    "pr_pairing.yaml",
]


def get_home_config_paths() -> list[Path]:
    """Get config file paths in user's home directory."""
    home = Path.home()
    return [
        home / ".config" / "pr_pairing" / "config.yaml",
        home / ".prpairingrc",
    ]


def find_config_file(config_path: Optional[str]) -> Optional[Path]:
    """Find config file from explicit path or search default locations.
    
    Search order:
    1. Explicit path (-c argument)
    2. ./.prpairingrc
    3. ./pr_pairing.yaml
    4. ~/.config/pr_pairing/config.yaml
    5. ~/.prpairingrc
    """
    if config_path:
        path = Path(config_path)
        if path.exists():
            return path
        return None
    
    for rel_path in CONFIG_SEARCH_PATHS:
        path = Path(rel_path)
        if path.exists():
            return path
    
    for abs_path in get_home_config_paths():
        if abs_path.exists():
            return abs_path
    
    return None


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    try:
        import yaml
    except ImportError:
        raise FileError("Config file support requires PyYAML. Install with: pip install pyyaml")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else {}
    except yaml.YAMLError as e:
        raise FileError(f"Error parsing config file {config_path}: {e}")
    except Exception as e:
        raise FileError(f"Error reading config file: {e}")


def normalize_bool(value: str) -> bool:
    """Convert string to boolean."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def merge_config(config: dict, args: argparse.Namespace) -> argparse.Namespace:
    """Merge config file with CLI arguments.
    
    CLI args > Config file > Defaults
    
    Config keys map to args:
    - reviewers -> args.reviewers
    - team_mode -> args.team_mode
    - knowledge_mode -> args.knowledge_mode
    - history -> args.history
    - verbose -> args.verbose (adjusts based on value)
    """
    defaults = {
        "reviewers": DEFAULT_REVIEWERS,
        "team_mode": False,
        "knowledge_mode": KnowledgeMode.ANYONE.value,
        "history": "./pairing_history.json",
        "verbose": 0,
    }
    
    config_key_to_arg = {
        "reviewers": "reviewers",
        "team_mode": "team_mode",
        "knowledge_mode": "knowledge_mode",
        "history": "history",
    }
    
    for config_key, arg_name in config_key_to_arg.items():
        current_value = getattr(args, arg_name)
        
        if current_value is None:
            value_from_config = config.get(config_key)
            if value_from_config is not None:
                value = value_from_config
                if config_key == "team_mode":
                    value = normalize_bool(value)
                elif config_key == "reviewers":
                    value = int(value)
                setattr(args, arg_name, value)
            else:
                setattr(args, arg_name, defaults[config_key])
        else:
            if arg_name not in defaults:
                defaults[arg_name] = None
            if current_value == defaults.get(arg_name):
                value_from_config = config.get(config_key)
                if value_from_config is not None:
                    value = value_from_config
                    if config_key == "team_mode":
                        value = normalize_bool(value)
                    elif config_key == "reviewers":
                        value = int(value)
                    setattr(args, arg_name, value)
    
    if args.verbose is None:
        verbose_config = config.get("verbose")
        if verbose_config is not None:
            if isinstance(verbose_config, bool):
                args.verbose = 1 if verbose_config else 0
            elif isinstance(verbose_config, int):
                args.verbose = verbose_config
        else:
            args.verbose = 0
    
    if args.quiet is None:
        args.quiet = 0
    
    return args


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
    return parser.parse_args()
