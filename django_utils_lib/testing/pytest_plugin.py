from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
)

import pytest
from constants import PACKAGE_NAME
from filelock import FileLock
from typing_extensions import NotRequired, TypedDict

from django_utils_lib.logger import build_heading_block, pkg_logger
from django_utils_lib.testing.utils import PytestNodeID, validate_requirement_tagging

BASE_DIR = Path(__file__).resolve().parent

# Due to the parallelized nature of xdist (we our library consumer might or might
# not be using), we are going to use a file-based system for implementing both
# a concurrency lock, as well as a way to easily share the metadata across
# processes.
temp_file_path = os.path.join(BASE_DIR, "test.temp.json")
temp_file_lock_path = f"{temp_file_path}.lock"
file_lock = FileLock(temp_file_lock_path)


TestStatus = Literal["PASS", "FAIL", ""]


class InvalidTestConfigurationError(Exception):
    pass


class PluginReportingConfiguration(TypedDict):
    csv_export_path: str
    """
    Where to save the CSV report to
    """
    omit_unexecuted_tests: NotRequired[bool]
    """
    If set to true, tests that were collected, but not executed, will be omitted
    from the generated report
    """


class PluginConfigurationItem(TypedDict):
    help: str
    default: Any
    type: Literal["string", "paths", "pathlist", "args", "linelist", "bool"]


PluginConfigKey = Literal[
    "auto_debug",
    "auto_debug_wait_for_connect",
    "mandate_requirement_markers",
    "reporting.csv_export_path",
    "reporting.omit_unexecuted_tests",
]

PluginConfigItems: Dict[PluginConfigKey, PluginConfigurationItem] = {
    "auto_debug": {
        "help": (
            "If true, the debugpy listener will be auto-invoked on the main pytest session."
            "\n"
            "You can also enable this by setting `{PACKAGE_NAME}_AUTO_DEBUG` as an environment variable."
        ),
        "type": "bool",
        "default": False,
    },
    "auto_debug_wait_for_connect": {
        "help": (
            "If true, or if the `auto_debug_wait_for_connect` env var is set, then the auto debug feature"
            " will wait for the debugger client to connect before starting tests"
        ),
        "type": "bool",
        "default": False,
    },
    "mandate_requirement_markers": {
        "help": (
            "If true, will validate that every test has a valid `pytest.mark.requirements`, and will"
            " also capture this metadata as part of the collected test data"
        ),
        "type": "bool",
        "default": False,
    },
    "reporting.csv_export_path": {
        "help": "If set, will save the test results to a CSV file after session completion",
        "type": "string",
        "default": None,
    },
    "reporting.omit_unexecuted_tests": {
        "help": "If set, will exclude tests that were collected but not executed from the test report CSV",
        "type": "bool",
        "default": False,
    },
}


class CollectedTestMetadata(TypedDict):
    """
    Metadata that is collected for each test "node"
    """

    node_id: PytestNodeID
    """
    node_id contains both the filepath and test name,
    in the format of `file_path::test_name`
    """

    doc_string: Optional[str]
    """
    The doc string attached to the given test (if applicable)
    """

    requirements: Optional[List[str]]
    """
    A list of requirements attached to the test node, passed via the `requirements()` marker
    """

    status: TestStatus


CollectedTestsMapping = Dict[PytestNodeID, CollectedTestMetadata]
"""
A mapping of pytest node IDs to their associated collected metadata
"""


class CollectedTests:
    """
    File-backed data-store for collected test info
    """

    def _get_data(self) -> CollectedTestsMapping:
        with file_lock:
            if not os.path.exists(temp_file_path):
                return {}
            with open(temp_file_path, "r") as f:
                return json.load(f)

    def __getitem__(self, node_id: PytestNodeID) -> CollectedTestMetadata:
        return self._get_data()[node_id]

    def __setitem__(self, node_id: str, item: CollectedTestMetadata):
        updated_data = self._get_data()
        updated_data[node_id] = item
        with file_lock:
            with open(temp_file_path, "w") as f:
                json.dump(updated_data, f)

    def update_test_status(self, node_id: PytestNodeID, updated_status: TestStatus):
        updated_data = self._get_data()
        updated_data[node_id]["status"] = updated_status
        with file_lock:
            with open(temp_file_path, "w") as f:
                json.dump(updated_data, f)


collected_tests = CollectedTests()


@pytest.hookimpl()
def pytest_addoption(parser: pytest.Parser):
    # Register all config key-pairs with INI parser
    for config_key, config_item in PluginConfigItems.items():
        parser.addini(name=config_key, **config_item)


@pytest.hookimpl()
def pytest_configure(config: pytest.Config):
    if hasattr(config, "workerinput"):
        return

    # Register markers
    config.addinivalue_line("markers", "requirements(requirements: List[str]): Attach requirements to test")

    # Register plugin
    plugin = CustomPytestPlugin(config)
    config.pluginmanager.register(plugin)
    pkg_logger.debug(f"{PACKAGE_NAME} plugin registered")
    plugin.auto_engage_debugger()


class CustomPytestPlugin:
    # Tell Pytest that this is not a test class
    __test__ = False

    def __init__(self, pytest_config: pytest.Config) -> None:
        self.pytest_config = pytest_config
        self.debugger_listening = False
        # We might or might not be running inside an xdist worker
        self._is_running_on_worker = False

    def get_config_val(self, config_key: PluginConfigKey):
        """
        Wrapper function just to add some extra type-safety around dynamic config keys
        """
        return self.pytest_config.getini(config_key)

    @property
    def auto_debug(self) -> bool:
        # Disable if CI is detected
        if os.getenv("CI", "").lower() == "true":
            return False
        return bool(self.get_config_val("auto_debug")) or bool(os.getenv(f"{PACKAGE_NAME}_AUTO_DEBUG", ""))

    @property
    def auto_debug_wait_for_connect(self) -> bool:
        return bool(self.get_config_val("auto_debug_wait_for_connect"))

    @property
    def mandate_requirement_markers(self) -> bool:
        return bool(self.get_config_val("mandate_requirement_markers"))

    @property
    def reporting_config(self) -> Optional[PluginReportingConfiguration]:
        csv_export_path = self.get_config_val("reporting.csv_export_path")
        if not isinstance(csv_export_path, str):
            return None
        return {
            "csv_export_path": csv_export_path,
            "omit_unexecuted_tests": bool(self.get_config_val("reporting.omit_unexecuted_tests")),
        }

    @property
    def is_running_on_worker(self) -> bool:
        return self._is_running_on_worker

    def auto_engage_debugger(self):
        if not self.auto_debug or self.is_running_on_worker:
            return
        try:
            # Disable noisy warning
            os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"
            import debugpy

            if self.debugger_listening or debugpy.is_client_connected():
                return

            DEBUGPY_PORT = int(os.environ.get("DEBUGPY_PORT_PYTEST", 5679))
            DEBUG_HOST = os.environ.get("DEBUGPY_PORT_PYTEST", "0.0.0.0")
            debugpy.listen((DEBUG_HOST, DEBUGPY_PORT))
            self.debugger_listening = True

            pkg_logger.warning(
                build_heading_block(
                    [
                        "debugpy is ON",
                        f"Host = {DEBUG_HOST}",
                        f"Port = {DEBUGPY_PORT}",
                    ]
                )
            )

            if self.auto_debug_wait_for_connect:
                pkg_logger.warning("Waiting for debugger to connect...")
                debugpy.wait_for_client()
        except Exception as err:
            pkg_logger.error("Error trying to invoke the auto-debugging functionality:")
            pkg_logger.error(err)

    @pytest.hookimpl()
    def pytest_collection_modifyitems(self, config: pytest.Config, items: List[pytest.Item]):
        # Configuration might have changed between sessionstart and modifyitems,
        # so recheck if debugger needs to be auto-engaged
        self.auto_engage_debugger()
        # We might have multiple errors, both in a single node, as well as across all
        errors: List[str] = []

        for item in items:
            requirements: List[str] = []
            if self.mandate_requirement_markers:
                validation_results = validate_requirement_tagging(item)
                errors.extend(validation_results["errors"])
                requirements = validation_results["validated_requirements"]

            doc_string: str = item.obj.__doc__ or ""  # type: ignore
            collected_tests[item.nodeid] = {
                "node_id": item.nodeid,
                "requirements": requirements,
                "doc_string": doc_string.strip(),
                "status": "",
            }

        if errors:
            raise InvalidTestConfigurationError(errors)

    @pytest.hookimpl()
    def pytest_sessionstart(self, session: pytest.Session):
        self._is_running_on_worker = getattr(session.config, "workerinput", None) is not None

        if self._is_running_on_worker:
            # Nothing to do here at the moment
            return

        # Init debugpy listener on main
        self.auto_engage_debugger()

    @pytest.hookimpl()
    def pytest_collection_finish(self, session: pytest.Session):
        self.auto_engage_debugger()

    @pytest.hookimpl()
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus):
        if not self.reporting_config:
            return
        collected_test_mappings = collected_tests._get_data()
        with open(self.reporting_config["csv_export_path"], "w") as csv_file:
            # Use keys of first entry, since all entries should have same keys
            fieldnames = collected_test_mappings[next(iter(collected_test_mappings))].keys()
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for test in collected_test_mappings.values():
                if self.reporting_config.get("omit_unexecuted_tests", False) and test["status"] == "":
                    pkg_logger.warning(f"Omitting {test['node_id']} from report; no status attached (test skipped?).")
                    continue
                writer.writerow(test)

    @pytest.hookimpl
    def pytest_runtest_logreport(self, report: pytest.TestReport):
        # Capture test outcomes and save to collection
        if report.when == "call":
            collected_tests.update_test_status(report.nodeid, "PASS" if report.passed else "FAIL")
