from dataclasses import dataclass, field
from typing import Any

from .models import Developer


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def validate_csv(developers: list[Developer]) -> ValidationResult:
    """Validate a list of Developer objects and return validation result."""
    errors = []
    warnings = []

    if not developers:
        errors.append("No developers found in input")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    check_required_columns(developers, errors)
    check_optional_columns(developers, errors, warnings)

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def check_required_columns(developers: list[Developer], errors: list[str]) -> None:
    """Check that required columns are present and valid."""
    has_reviewer = False
    for dev in developers:
        if dev.can_review:
            has_reviewer = True
            break

    if not has_reviewer:
        errors.append("No developers with can_review=true found")


def check_optional_columns(developers: list[Developer], errors: list[str], warnings: list[str]) -> None:
    """Validate optional columns and generate warnings/errors."""
    for idx, dev in enumerate(developers, start=1):
        if not dev.name or not dev.name.strip():
            errors.append(f"Row {idx}: Empty name")

        if dev.knowledge_level < 1 or dev.knowledge_level > 5:
            errors.append(f"Row {idx}: Invalid knowledge_level {dev.knowledge_level} (must be 1-5)")

        if dev.can_review and not isinstance(dev.can_review, bool):
            errors.append(f"Row {idx}: Invalid can_review value (expected true/false)")

        if dev.name and dev.name.strip() != dev.name:
            warnings.append(f"Row {idx}: Name has leading/trailing whitespace")


def print_validation_result(result: ValidationResult, filepath: str, developers: list[Developer] = None, verbosity: int = 0) -> None:
    """Print validation result in the specified format."""
    if verbosity < 0:
        return

    print("=== Input Validation ===")
    print(f"File: {filepath}")
    print()

    print("✓ Required columns: name, can_review")
    if developers:
        print(f"✓ {len(developers)} developers found")
    else:
        print(f"✓ 0 developers found")
    print()

    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  ⚠ {warning}")
        print()

    if result.errors:
        print("Errors:")
        for error in result.errors:
            print(f"  ✗ {error}")
        print()

    status = "PASSED" if result.is_valid else "FAILED"
    parts = []
    if result.error_count > 0:
        parts.append(f"{result.error_count} error{'s' if result.error_count != 1 else ''}")
    if result.warning_count > 0:
        parts.append(f"{result.warning_count} warning{'s' if result.warning_count != 1 else ''}")

    status_str = f"{status} ({', '.join(parts)})" if parts else status
    print(f"Status: {status_str}")
