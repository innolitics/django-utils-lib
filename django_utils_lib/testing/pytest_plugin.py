from __future__ import annotations

import csv
import json
import os
import pathlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Union,
    cast,
)

import pytest
import xdist
import xdist.dsession
import xdist.workermanage
from filelock import FileLock
from typing_extensions import NotRequired, TypedDict

from django_utils_lib.constants import PACKAGE_NAME, PACKAGE_NAME_SNAKE_CASE
from django_utils_lib.logger import pkg_logger
from django_utils_lib.logging_utils import build_heading_block
from django_utils_lib.testing.utils import PytestNodeID, is_main_pytest_runner, validate_requirement_tagging

BASE_DIR = Path(__file__).resolve().parent


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


class EnvVarOverride(TypedDict):
    name: str
    help: str


class PluginConfigurationItem(TypedDict):
    help: str
    default: Any
    type: Literal["string", "paths", "pathlist", "args", "linelist", "bool"]
    env_var_override: NotRequired[Optional[EnvVarOverride]]


PluginConfigKey = Literal[
    "auto_debug",
    "auto_debug_wait_for_connect",
    "mandate_requirement_markers",
    "reporting__csv_export_path",
    "reporting__omit_unexecuted_tests",
]

_AutoDebugEnvVarConfig: EnvVarOverride = {
    "name": f"{PACKAGE_NAME_SNAKE_CASE}_AUTO_DEBUG",
    "help": "If set to any truthy value (`bool()`), will enable auto-debugging. Unless `CI` is set to `true`.",
}

_AutoDebugWaitForConnectEnvVarConfig: EnvVarOverride = {
    "name": f"{PACKAGE_NAME_SNAKE_CASE}_AUTO_DEBUG_WAIT_FOR_CONNECT",
    "help": "If set to any truthy value (`bool()`), will enable waiting for debugger client to connect.",
}

_ReportingCSVExportPathEnvVarConfig: EnvVarOverride = {
    "name": f"{PACKAGE_NAME_SNAKE_CASE}_REPORTING__CSV_EXPORT_PATH",
    "help": "If set, will save the test results to a CSV file after session completion",
}

PluginConfigItems: Dict[PluginConfigKey, PluginConfigurationItem] = {
    "auto_debug": {
        "help": (
            "If true, the debugpy listener will be auto-invoked on the main pytest session."
            "\n"
            f"You can also enable this by setting `{PACKAGE_NAME_SNAKE_CASE}_AUTO_DEBUG` as an environment variable."
        ),
        "type": "bool",
        "default": False,
        "env_var_override": _AutoDebugEnvVarConfig,
    },
    "auto_debug_wait_for_connect": {
        "help": (
            "If true, then the auto debug feature" " will wait for the debugger client to connect before starting tests"
        ),
        "type": "bool",
        "default": False,
        "env_var_override": _AutoDebugWaitForConnectEnvVarConfig,
    },
    "mandate_requirement_markers": {
        "help": (
            "If true, will validate that every test has a valid `pytest.mark.requirements`, and will"
            " also capture this metadata as part of the collected test data"
        ),
        "type": "bool",
        "default": False,
    },
    "reporting__csv_export_path": {
        "help": "If set, will save the test results to a CSV file after session completion",
        "type": "string",
        "default": None,
        "env_var_override": _ReportingCSVExportPathEnvVarConfig,
    },
    "reporting__omit_unexecuted_tests": {
        "help": "If set, will exclude tests that were collected but not executed from the test report CSV",
        "type": "bool",
        "default": False,
    },
}


class InternalSessionConfig(TypedDict):
    global_session_id: str
    temp_shared_session_dir_path: str


# Note: Redundant typing of InternalSessionConfig, but likely unavoidable
# due to lack of type-coercion features in Python types
@dataclass
class InternalSessionConfigDataClass:
    global_session_id: str
    temp_shared_session_dir_path: str


class InternalWorkerConfig(InternalSessionConfig):
    # These values are provided by xdist automatically
    workerid: str
    """
    Auto-generated worker ID (`gw0`, `gw1`, etc.)
    """
    workercount: int
    testrunuid: str
    # Our own injected values
    temp_worker_dir_path: str


@dataclass
class WorkerConfigInstance:
    workerinput: InternalWorkerConfig


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

    def __init__(self, run_id: str) -> None:
        """
        Args:
            run_id: This should be a global session ID, unless you want to isolate results by worker
        """
        self.tmp_dir_path = os.path.join(BASE_DIR, ".pytest_run_cache", run_id)
        os.makedirs(self.tmp_dir_path, exist_ok=True)
        # Due to the parallelized nature of xdist (we our library consumer might or might
        # not be using), we are going to use a file-based system for implementing both
        # a concurrency lock, as well as a way to easily share the metadata across
        # processes.
        self.temp_file_path = os.path.join(self.tmp_dir_path, "test.temp.json")
        self.temp_file_lock_path = f"{self.temp_file_path}.lock"
        self.file_lock = FileLock(self.temp_file_lock_path)

    def _get_data(self) -> CollectedTestsMapping:
        with self.file_lock:
            if not os.path.exists(self.temp_file_path):
                return {}
            with open(self.temp_file_path, "r") as f:
                return json.load(f)

    def __getitem__(self, node_id: PytestNodeID) -> CollectedTestMetadata:
        return self._get_data()[node_id]

    def __setitem__(self, node_id: str, item: CollectedTestMetadata):
        updated_data = self._get_data()
        updated_data[node_id] = item
        with self.file_lock:
            with open(self.temp_file_path, "w") as f:
                json.dump(updated_data, f)

    def update_test_status(self, node_id: PytestNodeID, updated_status: TestStatus):
        updated_data = self._get_data()
        updated_data[node_id]["status"] = updated_status
        with self.file_lock:
            with open(self.temp_file_path, "w") as f:
                json.dump(updated_data, f)


@pytest.hookimpl()
def pytest_addoption(parser: pytest.Parser):
    # Register all config key-pairs with INI parser
    for config_key, config_item in PluginConfigItems.items():
        parser.addini(
            name=config_key, help=config_item["help"], default=config_item["default"], type=config_item["type"]
        )


@pytest.hookimpl()
def pytest_configure(config: pytest.Config):
    # Register markers
    # Note: This should be done every time (don't wrap in `is_main_pytest_runner` check)
    config.addinivalue_line("markers", "requirements(requirements: List[str]): Attach requirements to test")


@pytest.hookimpl()
def pytest_sessionstart(session: pytest.Session):
    if is_main_pytest_runner(session):
        # If we are on the main runner, this is either a non-xdist run, or
        # this is the main xdist process, before nodes been distributed.
        # Regardless, we should set up a shared temporary directory, which can
        # be shared among all n{0,} nodes
        global_session_id = uuid.uuid4().hex
        temp_shared_session_dir_path = os.path.join(BASE_DIR, ".pytest_run_cache", global_session_id)
        pathlib.Path(temp_shared_session_dir_path).mkdir(parents=True, exist_ok=True)
        session_config = cast(InternalSessionConfigDataClass, session.config)
        session_config.global_session_id = global_session_id
        session_config.temp_shared_session_dir_path = temp_shared_session_dir_path

    plugin = CustomPytestPlugin(session.config)
    session.config.pluginmanager.register(plugin)
    pkg_logger.debug(f"{PACKAGE_NAME} plugin registered")
    plugin.auto_engage_debugger()


def pytest_configure_node(node: xdist.workermanage.WorkerController):
    """
    Special xdist-only hook, which is called as a node is configured, before instantiation & distribution

    This hook only runs on the main process (not workers), and is skipped entirely if xdist is not being used
    """
    worker_id: str = node.workerinput["workerid"]

    # Retrieve global shared session config
    session_config = cast(InternalSessionConfigDataClass, node.config)
    temp_shared_session_dir_path = session_config.temp_shared_session_dir_path

    # Construct worker-scoped temp directory
    temp_worker_dir_path = os.path.join(temp_shared_session_dir_path, worker_id)
    pathlib.Path(temp_worker_dir_path).mkdir(parents=True, exist_ok=True)

    # Copy worker-specific, as well as shared config values, into the node config
    node.workerinput["temp_worker_dir_path"] = temp_worker_dir_path
    node.workerinput["temp_shared_session_dir_path"] = temp_shared_session_dir_path
    node.workerinput["global_session_id"] = session_config.global_session_id


class CustomPytestPlugin:
    # Tell Pytest that this is not a test class
    __test__ = False

    def __init__(self, pytest_config: pytest.Config) -> None:
        self.pytest_config = pytest_config
        self.collected_tests = CollectedTests(self.get_internal_shared_config(pytest_config)["global_session_id"])
        self.debugger_listening = False
        # We might or might not be running inside an xdist worker
        self._is_running_on_worker = not is_main_pytest_runner(pytest_config)

    def get_global_config_val(self, config_key: PluginConfigKey):
        """
        Wrapper function just to add some extra type-safety around dynamic config keys
        """
        return self.pytest_config.getini(config_key)

    def get_internal_shared_config(
        self, pytest_obj: Union[pytest.Session, pytest.Config, pytest.FixtureRequest]
    ) -> InternalSessionConfig:
        """
        Utility function to get shared config values, because it can be a little tricky to know
        where to retrieve them from (for main vs worker)
        """
        config = pytest_obj if isinstance(pytest_obj, pytest.Config) else pytest_obj.config
        # If we are on the main runner, we can just directly access
        if is_main_pytest_runner(config):
            session_config = cast(InternalSessionConfigDataClass, config)
            return {
                "temp_shared_session_dir_path": session_config.temp_shared_session_dir_path,
                "global_session_id": session_config.global_session_id,
            }
        # If we are on a worker, we can retrieve the shared config values via the `workerinput` property
        worker_input = cast(WorkerConfigInstance, config).workerinput
        return worker_input

    @property
    def auto_debug(self) -> bool:
        # Disable if CI is detected
        if os.getenv("CI", "").lower() == "true":
            return False
        return bool(self.get_global_config_val("auto_debug")) or bool(os.getenv(_AutoDebugEnvVarConfig["name"], ""))

    @property
    def auto_debug_wait_for_connect(self) -> bool:
        return bool(self.get_global_config_val("auto_debug_wait_for_connect")) or bool(
            os.getenv(_AutoDebugWaitForConnectEnvVarConfig["name"], "")
        )

    @property
    def mandate_requirement_markers(self) -> bool:
        return bool(self.get_global_config_val("mandate_requirement_markers"))

    @property
    def reporting_config(self) -> Optional[PluginReportingConfiguration]:
        csv_export_path = os.getenv(_ReportingCSVExportPathEnvVarConfig["name"]) or self.get_global_config_val(
            "reporting__csv_export_path"
        )
        if not isinstance(csv_export_path, str):
            return None
        return {
            "csv_export_path": csv_export_path,
            "omit_unexecuted_tests": bool(self.get_global_config_val("reporting__omit_unexecuted_tests")),
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
            DEBUG_HOST = os.environ.get("DEBUGPY_HOST_PYTEST", "0.0.0.0")
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
            self.collected_tests[item.nodeid] = {
                "node_id": item.nodeid,
                "requirements": requirements,
                "doc_string": doc_string.strip(),
                "status": "",
            }

        if errors:
            raise InvalidTestConfigurationError(errors)

    @pytest.hookimpl()
    def pytest_sessionstart(self, session: pytest.Session):
        if not is_main_pytest_runner(session):
            self._is_running_on_worker = True
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
        collected_test_mappings = self.collected_tests._get_data()
        csv_export_path = self.reporting_config["csv_export_path"]
        # Ensure intermediate dirs
        pathlib.Path(csv_export_path).parent.mkdir(parents=True, exist_ok=True)
        with open(csv_export_path, "w") as csv_file:
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
            self.collected_tests.update_test_status(report.nodeid, "PASS" if report.passed else "FAIL")
