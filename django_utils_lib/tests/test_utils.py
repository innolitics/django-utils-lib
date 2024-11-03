import sys
from typing import List, Optional, TypedDict

import pytest

from django_utils_lib.cli_utils import MonkeyPatchedArgsWithExpandedRepeats


class RequirementValidationTestScenario(TypedDict):
    test_file_src: str
    expected_pass_count: int
    expected_err_string: Optional[str]


requirement_validation_scenarios: List[RequirementValidationTestScenario] = [
    # Completely missing requirements
    {
        "test_file_src": """
    def test_missing_requirements():
        pass
    """,
        "expected_pass_count": 0,
        "expected_err_string": ".*InvalidTestConfigurationError:.*py::test_missing_requirements "
        "missing `requirements`.*",
    },
    # Requirements included, but invalid format
    {
        "test_file_src": """
    import pytest
    @pytest.mark.requirements("Hello")
    def test_invalid_requirements():
        pass
    """,
        "expected_pass_count": 0,
        "expected_err_string": ".*InvalidTestConfigurationError: .*does not match pattern.*",
    },
    # Requirements included, but not sorted
    {
        "test_file_src": """
    import pytest
    @pytest.mark.requirements("REQ-001-002", "REQ-001-001")
    def test_unsorted_requirements():
        pass
    """,
        "expected_pass_count": 0,
        "expected_err_string": ".*InvalidTestConfigurationError: .*requirements are not sorted correctly*",
    },
    # Successful usage
    {
        "test_file_src": """
import pytest

@pytest.mark.requirements("REQ-004-001", "REQ-005-002")
def test_valid_requirements():
    pass
""",
        "expected_pass_count": 1,
        "expected_err_string": None,
    },
]


@pytest.mark.parametrize("scenario", requirement_validation_scenarios)
def test_requirement_validation(scenario: RequirementValidationTestScenario, pytester: pytest.Pytester):
    """
    Tests the requirements marker validation functionality of our pytest plugin
    """
    # Setup a testing environment with our plugin, and mandated requirement markers
    pytester.makeconftest("""
pytest_plugins = ["django_utils_lib.testing.pytest_plugin"]
""")
    pytester.makeini("""
[pytest]
mandate_requirement_markers = True
""")

    pytester.makepyfile(test_requirements_validation=scenario["test_file_src"])
    result = pytester.runpytest("test_requirements_validation.py")

    if scenario["expected_err_string"]:
        result.stdout.re_match_lines([scenario["expected_err_string"]])
    else:
        result.stdout.no_re_match_line(".*InvalidTestConfigurationError.*")

    result.assert_outcomes(passed=scenario["expected_pass_count"])


class MonkeyPatchedArgsWithExpandedRepeatsTestCase(TypedDict):
    input_args: List[str]
    args_to_expand: List[str]
    expected_patched_args: List[str]


monkey_patched_args_with_expanded_repeats_test_cases: List[MonkeyPatchedArgsWithExpandedRepeatsTestCase] = [
    # Fairly simple example
    {
        "input_args": ["a", "b", "--author", "Mary Shelley", "Stanisław Lem"],
        "args_to_expand": ["--author"],
        "expected_patched_args": ["a", "b", "--author", "Mary Shelley", "--author", "Stanisław Lem"],
    },
    # More complicated, multiple items to patch, with non-patching args options between
    {
        "input_args": [
            "a",
            "--files",
            "file_a.txt",
            "file_b.txt",
            "--no-pager",
            "-d",
            "--parsers",
            "txt",
            "md",
            "--debug",
        ],
        "args_to_expand": ["--files", "--parsers"],
        "expected_patched_args": [
            "a",
            "--files",
            "file_a.txt",
            "--files",
            "file_b.txt",
            "--no-pager",
            "-d",
            "--parsers",
            "txt",
            "--parsers",
            "md",
            "--debug",
        ],
    },
]


@pytest.mark.parametrize("test_case", monkey_patched_args_with_expanded_repeats_test_cases)
def test_MonkeyPatchedArgsWithExpandedRepeats(test_case: MonkeyPatchedArgsWithExpandedRepeatsTestCase):
    """
    Tests the `MonkeyPatchedArgsWithExpandedRepeats` context manager
    """
    sys.argv = test_case["input_args"]
    with MonkeyPatchedArgsWithExpandedRepeats(args_to_expand=test_case["args_to_expand"]):
        assert sys.argv == test_case["expected_patched_args"]
    assert sys.argv == test_case["input_args"]
