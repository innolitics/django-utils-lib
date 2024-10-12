# Django Utils Lib

> A bundle of useful utility functions and helpers for working with Django


## Core Features

- Pytest plugin, with commonly needed items
    - Support for automated debugpy listener
    - Support for `requirements()` markers
    - Support for test collection, with CSV export (including with xdist)
- Logging utils (presets, formatters, etc.)
- CLI / pre-built commands (see [](./django_utils_lib/commands.py))
- CLI Utils


## Installing and Using (as a library)

While this repo is private, you can still install it in various projects by using the git origin as the source.

For example, [with Poetry](https://python-poetry.org/docs/dependency-specification/#git-dependencies), you can use:

```bash
poetry add git+https://github.com/innolitics/django-utils-lib.git#REFERENCE
```

> [!WARNING]
> Under the hood, your package manager needs to be able to authenticate against the git URL that you use. Locally, this should "Just Work", but in CI, you will need to give CI a token to access the repo (even if CI is running inside another `github.com/innolitics` repo).
>
> For CI purposes, you can use a read-only [GitHub deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys), as an easier alternative to managing PATs or fine-grained access tokens.

## Pytest plugin

### Pytest Plugin - Discovery / Registration

This package is not using pytests [automated entry points](https://docs.pytest.org/en/stable/how-to/writing_plugins.html#pip-installable-plugins), instead requiring that users manually opt-in to plugin usage (since you might want other utilities in this package without enabling the pytest plugin part of it).

To tell Pytest to use the plugin, the easiest way is to stick this in your highest level `.conftest.py` (aka the _root_ config):

```py
pytest_plugins = ["django_utils_lib.testing.pytest_plugin"]
```


### Pytest Plugin - Configuration

> [!TIP]
> Note: This table was auto-generated from the source-code (and can be re-generated) via `task docs:pytest_plugin_table`

| Config Key | Type | Default | Help | Env Var? |
|------------|------|---------|------|---------------|
| `auto_debug` | `bool` | `False` | If true, the debugpy listener will be auto-invoked on the main pytest session.<br/>You can also enable this by setting `django_utils_lib_AUTO_DEBUG` as an environment variable. | `django_utils_lib_AUTO_DEBUG`: If set to any truthy value (`bool()`), will enable auto-debugging. Unless `CI` is set to `true`. |
| `auto_debug_wait_for_connect` | `bool` | `False` | If true, then the auto debug feature will wait for the debugger client to connect before starting tests | `django_utils_lib_AUTO_DEBUG_WAIT_FOR_CONNECT`: If set to any truthy value (`bool()`), will enable waiting for debugger client to connect. |
| `mandate_requirement_markers` | `bool` | `False` | If true, will validate that every test has a valid `pytest.mark.requirements`, and will also capture this metadata as part of the collected test data | N/A |
| `reporting__csv_export_path` | `string` | `None` | If set, will save the test results to a CSV file after session completion | `django_utils_lib_REPORTING__CSV_EXPORT_PATH`: If set, will save the test results to a CSV file after session completion |
| `reporting__omit_unexecuted_tests` | `bool` | `False` | If set, will exclude tests that were collected but not executed from the test report CSV | N/A |

## Development

This project uses [`task` (aka `go-task`)](https://github.com/go-task/task) for developer task management and execution. [The `Taskfile.yml` file](./Taskfile.yml) serves as a way to organize these commands, as well as a form of documentation and easy entrypoint into getting started with the project.

You can use `task --list-all` to see all available `task` commands.

### Local Installation Cross-Directory

If you want to install a local development version of this library, in a different directory / project, you should be able to use the local path of the library in most standard Python package managers.

For example, this can be accomplished with Poetry with the following:

```bash
poetry add --editable ${LOCAL_PATH_TO_THIS_DIRECTORY}
```

### Publishing

TBD; right now this is only available internally at Innolitics (and/or for our clients), as a private repo.
