from .models import PRPairingError
from .rules import (
    YAML_AVAILABLE,
    load_rules_from_file,
    load_csv_rules_as_dict,
    load_yaml_rules_as_dict,
)


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
    return load_csv_rules_as_dict(filepath, "developer", "required_reviewer")


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
    return load_yaml_rules_as_dict(filepath, "developer", "required_reviewers", root_key="requirements")


def load_requirements(filepath: str, valid_developers: set[str]) -> dict[str, list[str]]:
    """Load required reviewers from file (auto-detect format by extension)."""
    return load_rules_from_file(  # type: ignore[return-value]
        filepath,
        key_field="developer",
        value_field="required_reviewer",
        valid_keys=valid_developers,
        valid_values=valid_developers,
        as_dict=True,
        root_key="requirements",
    )


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
