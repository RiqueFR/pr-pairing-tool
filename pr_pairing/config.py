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
    - no_balance -> args.no_balance
    - exclude -> args.exclude (list)
    - exclude_file -> args.exclude_file
    - require -> args.require (list)
    - require_file -> args.require_file
    - strict -> args.strict
    - output -> args.output
    - output_format -> args.output_format
    - quiet -> args.quiet
    """
    defaults = {
        "reviewers": DEFAULT_REVIEWERS,
        "team_mode": False,
        "knowledge_mode": KnowledgeMode.ANYONE.value,
        "history": "./pairing_history.json",
        "verbose": 0,
        "no_balance": False,
        "exclude": [],
        "exclude_file": None,
        "require": [],
        "require_file": None,
        "strict": False,
        "output": None,
        "output_format": None,
        "dry_run": False,
        "fresh": False,
        "quiet": 0,
    }
    
    config_key_to_arg = {
        "reviewers": "reviewers",
        "team_mode": "team_mode",
        "knowledge_mode": "knowledge_mode",
        "history": "history",
        "no_balance": "no_balance",
        "exclude": "exclude",
        "exclude_file": "exclude_file",
        "require": "require",
        "require_file": "require_file",
        "strict": "strict",
        "output": "output",
        "output_format": "output_format",
        "dry_run": "dry_run",
        "fresh": "fresh",
        "quiet": "quiet",
    }
    
    list_keys = {"exclude", "require"}
    bool_keys = {"team_mode", "no_balance", "strict", "dry_run", "fresh"}
    int_keys = {"reviewers", "quiet"}
    
    for config_key, arg_name in config_key_to_arg.items():
        current_value = getattr(args, arg_name)
        
        if current_value is None:
            value_from_config = config.get(config_key)
            if value_from_config is not None:
                value = value_from_config
                if config_key in list_keys and isinstance(value, list):
                    pass
                elif config_key in bool_keys:
                    value = normalize_bool(value)
                elif config_key in int_keys:
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
                    if config_key in list_keys and isinstance(value, list):
                        pass
                    elif config_key in bool_keys:
                        value = normalize_bool(value)
                    elif config_key in int_keys:
                        value = int(value)
                    setattr(args, arg_name, value)
    
    verbose_from_config = config.get("verbose")
    if verbose_from_config is not None:
        if isinstance(verbose_from_config, bool):
            args.verbose = 1 if verbose_from_config else 0
        elif isinstance(verbose_from_config, int):
            args.verbose = verbose_from_config
    elif args.verbose is None:
        args.verbose = 0
    
    if args.quiet is None:
        args.quiet = 0
    
    return args
