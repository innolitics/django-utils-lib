import logging
from os import get_terminal_size
from typing import List

from django_utils_lib.constants import PACKAGE_NAME

pkg_logger = logging.getLogger(PACKAGE_NAME)
pkg_logger.setLevel(logging.INFO)


def build_heading_block(heading: str | List[str], border_width=2) -> str:
    """
    Generate a heading, like:
    ```
    ===============
    ==   Hello   ==
    ===============
    ```
    """
    terminal_width = get_terminal_size().columns
    heading_delim = "".ljust(terminal_width, "=")
    heading_lines = [heading_delim]

    # Leave space for border, plus one space on each side
    border = "=" * border_width
    border_width_total = border_width + 1

    for line in heading if isinstance(heading, list) else heading.splitlines():
        left_inner_padding = int(
            (terminal_width - len(line) - (border_width_total * 2)) / 2
        )
        right_inner_padding = int(
            terminal_width - left_inner_padding - len(line) - (border_width_total * 2)
        )
        heading_lines.append(
            f"{border} {' ' * left_inner_padding}{line}{' ' * right_inner_padding} {border}"
        )
    heading_lines.append(heading_delim)

    return "\n".join(heading_lines)
