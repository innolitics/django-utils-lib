import sys
from contextlib import ContextDecorator
from typing import Any, List

import rich.markup as rich_markup
from rich.console import Console


class AlwaysEscapeMarkupConsole(Console):
    """
    Wrapper around Rich's Console to force logging to alway use markup AND escape output

    Note: It would be nice to be able to use `console.push_render_hook` to implement
        escaping through a custom renderer hook, rather than having to subclass the
        entire `Console` class, but the render hook appears to come too late in the
        processing chain to be able to auto-escape.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._markup = True

    def log(self, *objects: Any, **kwargs: Any) -> None:
        return super().log(*[rich_markup.escape(o) for o in objects], **kwargs)

    def print(self, *objects: Any, **kwargs: Any) -> None:
        return super().print(*[rich_markup.escape(o) for o in objects], **kwargs)


class MonkeyPatchedArgsWithExpandedRepeats(ContextDecorator):
    """
    This is a decorator / context manager, to monkey-patch sys.argv to emulate a
    user using repeated argument names / IDs when in fact they just used one and
    provided a list afterwards.

    For example, this:

    ```
    ["convert", "--files", "a.txt", "b.txt"]
    ```

    would get transformed into:

    ```
    ["convert", "--files", "a.txt", "--files", "b.txt"]
    ```

    Useful for CLI arg parsers that are not equipped to handle lists for a single arg.

    WARNING: If using to get around the list restriction in Typer, please
    check if https://github.com/tiangolo/typer/pull/800 is merged, as that is planned
    to fix this issue.
    """

    def __init__(self, args_to_expand: List[str]):
        self.args_to_expand = args_to_expand

    def __enter__(self):
        self.original_args = sys.argv.copy()
        args = sys.argv.copy()
        patched_arg_list = []

        idx = 0
        while idx < len(args):
            arg = args[idx]
            if arg in self.args_to_expand:
                # Capture everything from current position, until next flag/opt or end of args,
                # and repeat the arg_id before each
                while idx + 1 < len(args) and not args[idx + 1].startswith("-"):
                    patched_arg_list.extend([arg, args[idx + 1]])
                    idx += 1
                idx += 1
            else:
                patched_arg_list.append(arg)
                idx += 1
        sys.argv = patched_arg_list

    def __exit__(self, *exc):
        sys.argv = self.original_args
