from pathlib import Path
from typing import List

import typer
from rich.console import Console

from django_utils_lib.commands import generate_combined_spdx_sbom_json as generate_combined_spdx_sbom_json_cmd

app = typer.Typer()
console = Console()


@app.command()
def generate_combined_spdx_sbom_json(
    sbom_paths: List[str],
    out_path: Path,
    merged_name="Combined SBOM",
    merged_namespace="https//localhost",
):
    out_json = generate_combined_spdx_sbom_json_cmd(sbom_paths, merged_name, merged_namespace)
    out_path.write_text(out_json)


if __name__ == "__main__":
    app()
