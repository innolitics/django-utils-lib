import sys
from typing import List, TypedDict

import pytest

from django_utils_lib.cli_utils import MonkeyPatchedArgsWithExpandedRepeats


def test_requirement_validation(pytester: pytest.Pytester):
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
    pytester.makepyfile(
        missing_requirements="""
def test_missing_requirements():
    pass
""",
        invalid_requirements="""
import pytest

@pytest.mark.requirements("Hello")
def test_invalid_requirements():
    pass
""",
        unsorted_requirements="""
import pytest

@pytest.mark.requirements("REQ-001-002", "REQ-001-001")
def test_unsorted_requirements():
    pass
""",
        valid_requirements="""
import pytest

@pytest.mark.requirements("REQ-004-001", "REQ-005-002")
def test_valid_requirements():
    pass
""",
    )

    # Completely missing requirements
    result = pytester.runpytest("missing_requirements.py")
    result.stdout.fnmatch_lines(
        ["*InvalidTestConfigurationError:*missing_requirements.py::test_missing_requirements missing `requirements`*"]
    )
    result.assert_outcomes(passed=0)

    # Requirements included, but invalid format
    result = pytester.runpytest("invalid_requirements.py")
    result.stdout.fnmatch_lines(["*InvalidTestConfigurationError: *does not match pattern*"])
    result.assert_outcomes(passed=0)

    # Requirements included, but not sorted
    result = pytester.runpytest("unsorted_requirements.py")
    result.stdout.fnmatch_lines(["*InvalidTestConfigurationError: *requirements are not sorted correctly*"])
    result.assert_outcomes(passed=0)

    result = pytester.runpytest("valid_requirements.py")
    result.stdout.no_fnmatch_line("*InvalidTestConfigurationError*")
    result.assert_outcomes(passed=1)


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
