from typing import Any

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
