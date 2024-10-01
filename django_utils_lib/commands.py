import json
from pathlib import Path
from typing import Dict, List


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
