from __future__ import annotations

import re
from typing import List, Tuple, cast

import pytest
from typing_extensions import TypedDict

PytestNodeID = str
"""
A pytest node ID follows the format of `file_path::test_name`
"""


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
