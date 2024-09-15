from __future__ import annotations

import re
from typing import List, Tuple, Union, cast

import pytest
from typing_extensions import TypedDict
from xdist import is_xdist_worker

PytestNodeID = str
"""
A pytest node ID follows the format of `file_path::test_name`
"""


def is_main_pytest_runner(pytest_obj: Union[pytest.Config, pytest.FixtureRequest, pytest.Session]):
    """
    Utility function that returns true only if we are in the main runner (not an xdist worker)

    This should work in both xdist and non-xdist modes of operation.
    """
    # Pytest config or worker node
    if isinstance(pytest_obj, pytest.Config) or hasattr(pytest_obj, "workerinput"):
        # The presence of "workerinput", on either a config or distributed node,
        # indicates we are on a worker
        return getattr(pytest_obj, "workerinput", None) is None

    # Pytest session objects or requests
    if hasattr(pytest_obj, "config"):
        return is_xdist_worker(pytest_obj) is False

    return False


class RequirementValidationResults(TypedDict):
    valid: bool
    errors: List[str]
    validated_requirements: List[str]


def validate_requirement_tagging(item: pytest.Item) -> RequirementValidationResults:
    test_name = item.nodeid
    errors: List[str] = []
    marker = item.get_closest_marker("requirements")
    marker_args = marker.args if marker else ()

    if not marker_args:
        return {
            "valid": False,
            "errors": [f"{test_name} missing `requirements` marker (or args)"],
            "validated_requirements": [],
        }

    if not all(isinstance(arg, str) for arg in marker_args):
        return {
            "valid": False,
            "errors": [f"{test_name} requirements must all be strings"],
            "validated_requirements": [],
        }

    requirements = cast(Tuple[str], marker_args)
    validated_requirements: List[str] = []
    # Verify that sort order is correct
    # E.g., req-001-001 should come before req-001-002
    for i in range(1, len(requirements)):
        if requirements[i] < requirements[i - 1]:
            errors.append(f"{test_name} requirements are not sorted correctly")
            break
    # Verify that it matches pattern (or is NA)
    for req in requirements:
        if not re.match(r"REQ-\d{3}-\d{3}", req) and req != "NA":
            errors.append(f"{test_name} requirement {req} does not match pattern REQ-###-###")
        else:
            validated_requirements.append(req)

    if not validated_requirements:
        errors.append(f"{test_name} has no valid requirements")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "validated_requirements": validated_requirements,
    }
