from shutil import get_terminal_size
from typing import Any, Dict, List, Literal, TypedDict, Union


def build_heading_block(heading: Union[str, List[str]], border_width=2) -> str:
    """
    Generate a heading, like:
    ```
    ===============
    ==   Hello   ==
    ===============
    ```
    """
    terminal_width = get_terminal_size(fallback=(80, 24)).columns
    heading_delim = "".ljust(terminal_width, "=")
    heading_lines = [heading_delim]

    # Leave space for border, plus one space on each side
    border = "=" * border_width
    border_width_total = border_width + 1

    for line in heading if isinstance(heading, list) else heading.splitlines():
        left_inner_padding = int((terminal_width - len(line) - (border_width_total * 2)) / 2)
        right_inner_padding = int(terminal_width - left_inner_padding - len(line) - (border_width_total * 2))
        heading_lines.append(f"{border} {' ' * left_inner_padding}{line}{' ' * right_inner_padding} {border}")
    heading_lines.append(heading_delim)

    return "\n".join(heading_lines)


LoggingFormatterConfig = TypedDict(
    "LoggingFormatterConfig",
    {"class": str, "format": str, "datefmt": str, "style": Literal["%", "{", "$"]},
    total=False,
)

LoggingFormatterPreset = Literal["with_line_numbers", "no_line_numbers"]
LoggingHandlerPreset = Literal["console", "console_no_line_number"]


class LoggingPresets:
    """
    These presets can be useful for working the Python standard `logging` library, as well as Django's
    logging configuration, which wraps the standard implementation.

    For more details, see:

    - [Python Docs - logging.config](https://docs.python.org/3/library/logging.config.html)
    - [Django Docs - Logging](https://docs.djangoproject.com/en/5.1/topics/logging/)
    """

    formatters: Dict[LoggingFormatterPreset, LoggingFormatterConfig] = {
        "with_line_numbers": {
            "format": "[%(name)s] [%(asctime)s] %(levelname)s - [%(filename)s:%(lineno)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "no_line_numbers": {
            "format": "[%(name)s] [%(asctime)s] %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }
    handlers: Dict[LoggingHandlerPreset, Dict[str, Any]] = {
        "console": {"class": "logging.StreamHandler", "formatter": "with_line_numbers"},
        "console_no_line_number": {"class": "logging.StreamHandler", "formatter": "no_line_numbers"},
    }
