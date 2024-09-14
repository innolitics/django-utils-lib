import pytest


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
