from pathlib import Path

from .models import FileError

YAML_AVAILABLE = True
try:
    import yaml
except ImportError:
    YAML_AVAILABLE = False


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
    import csv
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
    
    import yaml
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
