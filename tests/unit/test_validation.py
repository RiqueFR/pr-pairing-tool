import pytest
from pr_pairing.validation import (
    ValidationResult,
    validate_csv,
    check_required_columns,
    check_optional_columns,
)
from pr_pairing.models import Developer


class TestValidationResult:
    def test_validation_result_valid(self):
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        assert result.is_valid is True
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_validation_result_with_errors(self):
        result = ValidationResult(is_valid=False, errors=["error1"], warnings=["warning1"])
        assert result.is_valid is False
        assert result.error_count == 1
        assert result.warning_count == 1


class TestValidateCsv:
    def test_validate_csv_empty_developers(self):
        result = validate_csv([])
        assert result.is_valid is False
        assert "No developers found" in result.errors[0]

    def test_validate_csv_valid_developers(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=4),
        ]
        result = validate_csv(developers)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_csv_no_reviewers(self):
        developers = [
            Developer(name="Alice", can_review=False, team="frontend", knowledge_level=3),
            Developer(name="Bob", can_review=False, team="backend", knowledge_level=4),
        ]
        result = validate_csv(developers)
        assert result.is_valid is False
        assert any("can_review=true" in err for err in result.errors)

    def test_validate_csv_invalid_knowledge_level(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=6),
        ]
        result = validate_csv(developers)
        assert result.is_valid is False
        assert any("knowledge_level" in err and "must be 1-5" in err for err in result.errors)

    def test_validate_csv_knowledge_level_at_boundary(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=1),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=5),
        ]
        result = validate_csv(developers)
        assert result.is_valid is True


class TestCheckRequiredColumns:
    def test_check_required_columns_with_reviewers(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
        ]
        errors = []
        check_required_columns(developers, errors)
        assert len(errors) == 0

    def test_check_required_columns_no_reviewers(self):
        developers = [
            Developer(name="Alice", can_review=False, team="frontend", knowledge_level=3),
        ]
        errors = []
        check_required_columns(developers, errors)
        assert len(errors) == 1
        assert "can_review=true" in errors[0]


class TestCheckOptionalColumns:
    def test_check_optional_columns_valid(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=3),
        ]
        errors = []
        warnings = []
        check_optional_columns(developers, errors, warnings)
        assert len(errors) == 0
        assert len(warnings) == 0

    def test_check_optional_columns_invalid_knowledge_level_high(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=10),
        ]
        errors = []
        warnings = []
        check_optional_columns(developers, errors, warnings)
        assert len(errors) == 1
        assert "knowledge_level" in errors[0]
        assert "must be 1-5" in errors[0]

    def test_check_optional_columns_invalid_knowledge_level_low(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=0),
        ]
        errors = []
        warnings = []
        check_optional_columns(developers, errors, warnings)
        assert len(errors) == 1
        assert "knowledge_level" in errors[0]

    def test_check_optional_columns_whitespace_in_name(self):
        developers = [
            Developer(name="  Alice  ", can_review=True, team="frontend", knowledge_level=3),
        ]
        errors = []
        warnings = []
        check_optional_columns(developers, errors, warnings)
        assert len(warnings) == 1
        assert "whitespace" in warnings[0]

    def test_check_optional_columns_empty_name(self):
        developers = [
            Developer(name="", can_review=True, team="frontend", knowledge_level=3),
        ]
        errors = []
        warnings = []
        check_optional_columns(developers, errors, warnings)
        assert len(errors) == 1
        assert "Empty name" in errors[0]

    def test_check_optional_columns_whitespace_only_name(self):
        developers = [
            Developer(name="   ", can_review=True, team="frontend", knowledge_level=3),
        ]
        errors = []
        warnings = []
        check_optional_columns(developers, errors, warnings)
        assert len(errors) == 1
        assert "Empty name" in errors[0]
