from __future__ import annotations

import re
from typing import Dict, List, Tuple, Union, cast
from unittest import TestCase

import pytest
from django.contrib.auth import authenticate
from django.http import HttpRequest
from django.test.client import Client as _TestClient
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


class TestClient(_TestClient):
    """
    A Wrapper around Django's default TestClient to add a few extra features,
    such as compatibility with `django-axes`
    """

    # This is so that Pytest doesn't think this is itself a test
    __test__ = False

    def login(self, client_ip="127.0.0.1", **credentials) -> bool:
        """
        This overrides the `login` method from `ClientMixin`, to get it to work with
        the `django-axes` middleware, which requires a `HttpRequest` object as part of the
        authentication flow.
        """
        request = HttpRequest()
        request.META = {"REMOTE_ADDR": client_ip}
        user = authenticate(request=request, **credentials)
        if user:
            self._login(user)  # type: ignore[attr-defined]
            return True
        return False

    def post_json(self, path: str, data: Dict):
        return self.post(path, data=data, content_type="application/json")

    def patch_json(self, path: str, data: Dict):
        return self.patch(path, data=data, content_type="application/json")

    def get_json(self, path: str, *args, **kwargs):
        return self.get(path, *args, **kwargs).json()


class TestDataManager(TestCase):
    '''
    Wrapper class to help manage test data through the lifecycle of a test

    The normal pattern for using this would be sub-class it, and then expose it
    as a injected fixture. E.g.:

    ```python
    class MyTestDataManager(TestDataManager):
        pass

    @pytest.fixture
    def test_data(db) -> TestDataManager:
        """
        Fixture wrapper around test data manager
        """
        return TestDataManager()
    ```
    '''

    # Note: This overrides the default of the parent class, to use our
    # modified TestClient
    client: TestClient

    def __init__(self) -> None:
        super().__init__()
        self.client = TestClient()
