import json
import os
import sys
from pathlib import Path
from typing import Dict, Final, List, Optional, Union


def generate_combined_spdx_sbom_json(
    sbom_paths: List[str],
    merged_name="Combined SBOM",
    merged_namespace="https//localhost",
) -> str:
    """
    Combine multiple SPDX formatted JSON SBOMs, into a single JSON file

    Warning: This is a basic implementation that makes some assumptions about the
    validity of the input files and what sort of output is desired.
    """
    with open(sbom_paths[0], "r") as file:
        combined_sbom_json: Dict = json.load(file)
        expected_spdx_version = combined_sbom_json["spdxVersion"]
    combined_sbom_json["name"] = merged_name
    combined_sbom_json["documentNamespace"] = merged_namespace

    for sbom_path in sbom_paths:
        sbom_json = json.loads(Path(sbom_path).read_text())
        # Don't allow combining outputs with different versions
        assert sbom_json["spdxVersion"] == expected_spdx_version
        for sbom_key in ["files", "packages", "relationships"]:
            combined_sbom_json[sbom_key] += sbom_json[sbom_key]

    return json.dumps(combined_sbom_json, indent=2)


# Note: Capitalization does not matter, as these will be checked as case-insensitive
UNDERSTOOD_VERSION_CONTAINERS: Final = ["pyproject.toml", "package.json", "cargo.toml"]


def check_versions_in_sync(version_declaration_files: List[str], expected_version: Optional[str] = None):
    """
    Check that project version strings are in agreement, across multiple places where they are declared
    """
    for filepath in version_declaration_files:
        filename = os.path.basename(filepath).lower()
        if filename not in UNDERSTOOD_VERSION_CONTAINERS:
            raise ValueError(
                f"Not sure how to parse version string out of {filepath}. Accepted files are "
                f"{', '.join(UNDERSTOOD_VERSION_CONTAINERS)}"
            )
        extracted_version: Optional[Union[str, Dict]] = None

        with open(filepath, "r") as file:
            file_contents = file.read()

            if filename == "package.json":
                package_json = json.loads(file_contents)
                extracted_version = package_json["version"]

            elif filename == "pyproject.toml" or filename == "cargo.toml":
                if not sys.version_info >= (3, 11):
                    raise NotImplementedError("The TOML parser is only included with Python >= 3.11")
                import tomllib

                lookup_accessors = (
                    ["tool.poetry.version", "project.version"] if filename == "pyproject.toml" else ["package.version"]
                )

                project_toml = tomllib.loads(file_contents)
                for lookup_accessor in lookup_accessors:
                    if extracted_version is not None:
                        continue
                    try:
                        project_info = project_toml
                        for key in lookup_accessor.split("."):
                            project_info = project_info[key]
                        extracted_version = project_info
                    except KeyError:
                        pass

            assert isinstance(extracted_version, str), f"Could not find version info in {filepath}"
        if not expected_version:
            expected_version = extracted_version
            continue

        assert (
            extracted_version == expected_version
        ), f"Version mismatch in {filepath} - expected {expected_version}, got {extracted_version}"
