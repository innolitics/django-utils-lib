from pathlib import Path
from typing import Annotated, List

import typer
from rich.console import Console

from django_utils_lib.commands import check_versions_in_sync
from django_utils_lib.commands import generate_combined_spdx_sbom_json as generate_combined_spdx_sbom_json_cmd

app = typer.Typer()
console = Console()


@app.command()
def generate_combined_spdx_sbom_json(
    sbom_paths: Annotated[List[str], typer.Argument()],
    out_path: Annotated[Path, typer.Option("--out")],
    merged_name: Annotated[str, typer.Option("--merged-name")] = "Combined SBOM",
    merged_namespace: Annotated[str, typer.Option("--merged-namespace")] = "https://localhost",
):
    out_json = generate_combined_spdx_sbom_json_cmd(sbom_paths, merged_name, merged_namespace)
    out_path.write_text(out_json)


app.command()(check_versions_in_sync)

if __name__ == "__main__":
    app()
