from pathlib import Path
import csv

from .models import FileError

YAML_AVAILABLE = True
try:
    import yaml
except ImportError:
    YAML_AVAILABLE = False


def load_csv_rules_as_dict(
    filepath: str,
    key_column: str,
    value_column: str,
) -> dict[str, list[str]]:
    """Load rules from CSV file as dict."""

    result: dict[str, list[str]] = {}

    try:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row.get(key_column, "").strip()
                value = row.get(value_column, "").strip()
                if key and value:
                    if key not in result:
                        result[key] = []
                    result[key].append(value)
    except FileNotFoundError:
        raise FileError(f"Rules file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading rules file: {e}")
    return result


def load_csv_rules_as_set(
    filepath: str,
    key_column: str,
    value_column: str,
) -> set[tuple[str, str]]:
    """Load rules from CSV file as set."""
    result: set[tuple[str, str]] = set()

    try:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row.get(key_column, "").strip()
                value = row.get(value_column, "").strip()
                if key and value:
                    result.add((key, value))
    except FileNotFoundError:
        raise FileError(f"Rules file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading rules file: {e}")
    return result


def load_yaml_rules_as_dict(
    filepath: str,
    key_field: str,
    value_field: str,
    root_key: str = "rules",
) -> dict[str, list[str]]:
    """Load rules from YAML file as dict."""
    if not YAML_AVAILABLE:
        raise FileError(
            "YAML support requires PyYAML. Install with: pip install pyyaml"
        )

    result: dict[str, list[str]] = {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return result

        items = data.get(root_key, [])
        for item in items:
            key = item.get(key_field, "").strip()
            values = item.get(value_field, [])

            if key and values:
                result[key] = values
    except FileNotFoundError:
        raise FileError(f"Rules file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading rules file: {e}")
    return result


def load_yaml_rules_as_set(
    filepath: str,
    key_field: str,
    value_field: str,
) -> set[tuple[str, str]]:
    """Load rules from YAML file as set."""
    if not YAML_AVAILABLE:
        raise FileError(
            "YAML support requires PyYAML. Install with: pip install pyyaml"
        )

    result: set[tuple[str, str]] = set()

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return result

        items = data.get("rules", [])
        for item in items:
            key = item.get(key_field, "").strip()
            values = item.get(value_field, [])

            if key and values:
                if isinstance(values, list):
                    for v in values:
                        result.add((key, v))
                else:
                    result.add((key, values))
    except FileNotFoundError:
        raise FileError(f"Rules file not found: {filepath}")
    except Exception as e:
        raise FileError(f"Error reading rules file: {e}")
    return result


def load_rules_from_file(
    filepath: str,
    key_field: str,
    value_field: str,
    valid_keys: set[str],
    valid_values: set[str],
    as_dict: bool = True,
    root_key: str = "rules",
):
    """Load rules from file with validation."""
    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        if as_dict:
            rules = load_yaml_rules_as_dict(filepath, key_field, value_field, root_key)
            rules = _validate_dict_rules(rules, valid_keys, valid_values, filepath)
        else:
            rules = load_yaml_rules_as_set(filepath, key_field, value_field)
            rules = _validate_set_rules(rules, valid_keys, valid_values, filepath)
    elif suffix == ".csv":
        if as_dict:
            rules = load_csv_rules_as_dict(filepath, key_field, value_field)
            rules = _validate_dict_rules(rules, valid_keys, valid_values, filepath)
        else:
            rules = load_csv_rules_as_set(filepath, key_field, value_field)
            rules = _validate_set_rules(rules, valid_keys, valid_values, filepath)
    else:
        raise FileError(f"Unsupported rules file format: {suffix}. Use .csv or .yaml")

    return rules


def _validate_dict_rules(
    rules: dict[str, list[str]],
    valid_keys: set[str],
    valid_values: set[str],
    filepath: str,
) -> dict[str, list[str]]:
    """Validate dict-style rules."""
    invalid_keys = [k for k in rules if k not in valid_keys]
    if invalid_keys:
        raise FileError(f"Invalid developers in {filepath}: {', '.join(invalid_keys)}")

    all_values: set = set()
    for values in rules.values():
        all_values.update(values)

    invalid_values = [v for v in all_values if v not in valid_values]
    if invalid_values:
        raise FileError(f"Invalid values in {filepath}: {', '.join(invalid_values)}")

    return rules


def _validate_set_rules(
    rules: set[tuple[str, str]],
    valid_keys: set[str],
    valid_values: set[str],
    filepath: str,
) -> set[tuple[str, str]]:
    """Validate set-style rules."""
    all_items: set = set()
    for k, v in rules:
        all_items.add(k)
        all_items.add(v)

    invalid_items = [
        i for i in all_items if i not in valid_keys or i not in valid_values
    ]
    if invalid_items:
        raise FileError(f"Invalid developers in {filepath}: {', '.join(invalid_items)}")

    return rules


def load_exclusions_from_csv(filepath: str) -> set[tuple[str, str]]:
    """Load exclusion pairs from CSV file."""
    return load_csv_rules_as_set(filepath, "developer", "excluded_reviewer")


def load_exclusions_from_yaml(filepath: str) -> set[tuple[str, str]]:
    """Load exclusion pairs from YAML file."""
    if not YAML_AVAILABLE:
        raise FileError(
            "YAML support requires PyYAML. Install with: pip install pyyaml"
        )

    exclusions: set[tuple[str, str]] = set()

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
        exclusions = load_exclusions_from_yaml(filepath)
    elif suffix == ".csv":
        exclusions = load_exclusions_from_csv(filepath)
    else:
        raise FileError(
            f"Unsupported exclusion file format: {suffix}. Use .csv or .yaml"
        )

    return _validate_set_rules(exclusions, valid_developers, valid_developers, filepath)


def parse_exclusion_string(
    exclusion: str, valid_developers: set[str]
) -> tuple[str, str] | None:
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
