import pytest

from pr_pairing import normalize_bool


class TestUtilityFunctions:
    @pytest.mark.parametrize("value,expected", [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("y", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("n", False),
    ])
    def test_normalize_bool(self, value, expected):
        assert normalize_bool(value) == expected

    def test_normalize_bool_boolean_input(self):
        assert normalize_bool(True) is True
        assert normalize_bool(False) is False
