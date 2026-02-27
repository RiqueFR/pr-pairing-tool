from pathlib import Path
from typing import Optional

from .models import FileError, PRPairingError

YAML_AVAILABLE = True
try:
    import yaml
except ImportError:
    YAML_AVAILABLE = False


def parse_requirement_string(requirement: str, valid_developers: set[str]) -> tuple[str, str] | None:
    """Parse requirement string in format DEV1:DEV2 (DEV1 must review DEV2)."""
    try:
        developer, reviewer = requirement.split(":")
        developer = developer.strip()
        reviewer = reviewer.strip()
        if not developer or not reviewer:
            return None
        if developer == reviewer:
            return None
        if developer not in valid_developers:
            return None
        if reviewer not in valid_developers:
            return None
        return (developer, reviewer)
    except ValueError:
        return None


def load_requirements_from_csv(filepath: str) -> dict[str, list[str]]:
    """Load required reviewers from CSV file.
    
    CSV format:
        developer,required_reviewer
        Bob,Alice
        Bob,Charlie
    
    Returns dict: {developer: [required_reviewers]}
    """
    import csv
    requirements = {}
    try:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                developer = row.get("developer", "").strip()
                reviewer = row.get("required_reviewer", "").strip()
                if developer and reviewer:
                    if developer not in requirements:
                        requirements[developer] = []
                    requirements[developer].append(reviewer)
    except FileNotFoundError:
        raise FileError(f"Requirements file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading requirements file: {e}")
    return requirements


def load_requirements_from_yaml(filepath: str) -> dict[str, list[str]]:
    """Load required reviewers from YAML file.
    
    YAML format:
        requirements:
          - developer: Bob
            required_reviewers:
              - Alice
              - Charlie
    
    Returns dict: {developer: [required_reviewers]}
    """
    if not YAML_AVAILABLE:
        raise FileError("YAML support requires PyYAML. Install with: pip install pyyaml")
    
    import yaml
    requirements = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data:
            return requirements
        
        requirements_list = data.get("requirements", [])
        for item in requirements_list:
            developer = item.get("developer", "").strip()
            reviewers = item.get("required_reviewers", [])
            if developer and reviewers:
                requirements[developer] = reviewers
    except FileNotFoundError:
        raise FileError(f"Requirements file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading requirements file: {e}")
    return requirements


def load_requirements(filepath: str, valid_developers: set[str]) -> dict[str, list[str]]:
    """Load required reviewers from file (auto-detect format by extension)."""
    path = Path(filepath)
    suffix = path.suffix.lower()
    
    if suffix in (".yaml", ".yml"):
        requirements = load_requirements_from_yaml(filepath)
    elif suffix == ".csv":
        requirements = load_requirements_from_csv(filepath)
    else:
        raise FileError(f"Unsupported requirements file format: {suffix}. Use .csv or .yaml")
    
    invalid_developers = [dev for dev in requirements if dev not in valid_developers]
    if invalid_developers:
        raise FileError(f"Invalid developers in requirements file: {', '.join(invalid_developers)}")
    
    all_reviewers = set()
    for reviewers in requirements.values():
        all_reviewers.update(reviewers)
    invalid_reviewers = [rev for rev in all_reviewers if rev not in valid_developers]
    if invalid_reviewers:
        raise FileError(f"Invalid reviewers in requirements file: {', '.join(invalid_reviewers)}")
    
    return requirements


def parse_requirements_cli(requirements: list[str], valid_developers: set[str]) -> dict[str, list[str]]:
    """Parse requirements list from CLI arguments."""
    result = {}
    for req in requirements:
        parsed = parse_requirement_string(req, valid_developers)
        if parsed:
            developer, reviewer = parsed
            if developer not in result:
                result[developer] = []
            result[developer].append(reviewer)
    return result


def check_conflicts(
    requirements: dict[str, list[str]],
    exclusions: set[tuple[str, str]]
) -> list[str]:
    """Check for conflicts between requirements and exclusions.
    
    Returns list of conflict error messages.
    """
    conflicts = []
    for developer, reviewers in requirements.items():
        for reviewer in reviewers:
            if (developer, reviewer) in exclusions:
                conflicts.append(
                    f"Conflict: '{developer}:{reviewer}' is both required and excluded"
                )
    return conflicts
