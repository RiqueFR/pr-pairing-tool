from .rules import (
    load_exclusions,
    load_exclusions_from_csv,
    load_exclusions_from_yaml,
    parse_exclusion_string,
)


def parse_exclusions_cli(exclusions: list[str], valid_developers: set[str]) -> set[tuple[str, str]]:
    """Parse exclusion list from CLI arguments."""
    result = set()
    for exc in exclusions:
        parsed = parse_exclusion_string(exc, valid_developers)
        if parsed:
            result.add(parsed)
    return result
