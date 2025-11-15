from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple, Union

LINE_LENGTH = 96
INNER_DIVIDER = object()


def _ansi(code: str):
    def apply(text: str) -> str:
        return f"\x1b[{code}m{text}\x1b[0m"

    return apply


class Styles:
    bold = staticmethod(_ansi("1"))
    dim = staticmethod(_ansi("2"))
    red = staticmethod(_ansi("31"))
    yellow = staticmethod(_ansi("33"))
    gray = staticmethod(_ansi("90"))


styles = Styles()


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def format_metadata_rows(entries: Sequence[Tuple[str, str]]) -> List[str]:
    if not entries:
        return []
    width = max(len(strip_ansi(label)) for label, _ in entries)
    return [f"{styles.dim(label.ljust(width))}: {value}" for label, value in entries]


def format_sentence_count(count: int, relation: str | None) -> str:
    tag = ""
    if relation == "more":
        tag = f" {styles.yellow('(more)')}"
    elif relation == "fewer":
        tag = f" {styles.red('(fewer)')}"
    return f"{count}{tag}"


def format_preview_entry(
    index_label: str,
    label: str,
    content: str | None,
    highlight: bool = False,
) -> str:
    marker = "(!)" if highlight else "·"
    padded_marker = marker.ljust(3)
    marker_display = (
        styles.red("(!)") if highlight else styles.gray("·")
    ) + " " * (len(padded_marker) - 1)

    safe_content = content if content else styles.red("(missing)")
    plain_index = index_label if label == "zh" else " " * len(index_label)
    styled_index = (
        styles.bold(index_label) if label == "zh" else " " * len(index_label)
    )

    raw_prefix = f"{padded_marker} {plain_index} {label}: "
    styled_prefix = f"{marker_display} {styled_index} {styles.dim(label)}: "
    indented = safe_content.replace("\n", f"\n{' ' * len(raw_prefix)}")
    return f"{styled_prefix}{indented}"


def format_block(title: str, rows: Sequence[Union[str, object]]) -> str:
    normalized: List[Union[str, object]] = []
    for row in rows:
        if row is INNER_DIVIDER:
            normalized.append(INNER_DIVIDER)
        else:
            text = str(row)
            normalized.extend(text.splitlines() or [""])

    title_plain = strip_ansi(title)
    trailing = max(2, LINE_LENGTH - (len(title_plain) + 4))
    heading = f"{styles.yellow('──')} {styles.bold(title)} {styles.yellow('─' * trailing)}"
    divider = styles.yellow("─" * LINE_LENGTH)

    formatted: List[str] = []
    for entry in normalized:
        if entry is INNER_DIVIDER:
            formatted.append(divider)
        elif entry == "":
            formatted.append("")
        else:
            formatted.append(f"  {entry}")

    collapsed: List[str] = []
    for line in ["", heading, "", *formatted, "", divider, ""]:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)

    return "\n".join(collapsed)


def print_block(title: str, rows: Sequence[Union[str, object]] | None = None) -> None:
    print(format_block(title, rows or []))


def print_warning(title: str, rows: Sequence[Union[str, object]] | None = None) -> None:
    print_block(f"⚠️  {title}", rows or [])

