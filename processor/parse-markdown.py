from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any


BlockType = Literal["text", "list", "code"]


@dataclass
class Block:
    id: str
    type: BlockType
    source: Optional[str] = None  # original markdown text for text/code blocks
    items: Optional[List[str]] = None  # for list blocks


# Hardcoded English titles for now; extend as needed.
CHAPTER_TITLE_EN: Dict[int, str] = {
    1: "Clarify Meaning",
    2: "Variables",
    3: "Arithmetics",
    4: "Decision-making",
    5: "Loops",
    6: "Matrices",
    7: "Language",
    # 8+: fill in later if you want specific translations
}


def parse_heading_and_body(lines: List[str]) -> tuple[str, List[str]]:
    """
    Extract chapter title from the first-level heading and return
    (title, remaining body lines).
    """
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            body = lines[idx + 1 :]
            return title, body

    raise ValueError("No first-level heading ('# ...') found in chapter.")


def parse_blocks(body_lines: List[str]) -> List[Block]:
    """
    Turn markdown body into a list of logical blocks:
    - text blocks (paragraphs)
    - list blocks (grouped consecutive '- ' items)
    - code blocks (fenced with ```).
    """
    blocks: List[Block] = []
    block_counter = 1

    in_code_block = False
    code_lines: List[str] = []
    code_fence_start_line: Optional[str] = None  # track the opening fence line

    current_text_lines: List[str] = []
    current_list_items: List[str] = []
    current_list_raw_lines: List[str] = []  # track original markdown for list items
    in_list_block = False

    def flush_text():
        nonlocal block_counter, current_text_lines
        if current_text_lines:
            # Preserve original markdown text (including inline code markers, etc.)
            source = "\n".join(line.rstrip() for line in current_text_lines).strip()
            if source:
                blocks.append(
                    Block(
                        id=f"b{block_counter}",
                        type="text",
                        source=source,
                    )
                )
                block_counter += 1
            current_text_lines = []

    def flush_list():
        nonlocal block_counter, current_list_items, current_list_raw_lines, in_list_block
        if current_list_items:
            # Strip whitespace from items, but keep text as-is otherwise.
            items = [item.strip() for item in current_list_items if item.strip()]
            if items:
                blocks.append(
                    Block(
                        id=f"b{block_counter}",
                        type="list",
                        items=items,
                    )
                )
                block_counter += 1
            current_list_items = []
            current_list_raw_lines = []
        in_list_block = False

    def flush_code():
        nonlocal block_counter, code_lines, code_fence_start_line, in_code_block
        if code_lines:
            # Preserve original markdown with fence markers
            source = "\n".join(code_lines)
            if code_fence_start_line:
                # Include both opening and closing fences
                source = f"{code_fence_start_line}\n{source}\n```"
            else:
                # Fallback if fence line wasn't captured
                source = f"```\n{source}\n```"
            blocks.append(
                Block(
                    id=f"b{block_counter}",
                    type="code",
                    source=source,
                )
            )
            block_counter += 1
        code_lines = []
        code_fence_start_line = None
        in_code_block = False

    for raw_line in body_lines:
        line = raw_line.rstrip("\n")

        # Handle fenced code blocks
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code_block:
                # Starting a new code block: flush any pending text/list.
                flush_text()
                flush_list()
                in_code_block = True
                code_fence_start_line = line  # preserve original fence line
                code_lines = []
            else:
                # Ending current code block
                flush_code()
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Outside code blocks: handle blank lines
        if not stripped:
            # Blank lines: flush text blocks, but keep list blocks open
            # (blank lines between list items are part of the same list)
            flush_text()
            # Don't flush_list() here - wait to see if next line is also a list item
            continue

        # List item?
        lstripped = line.lstrip()
        if lstripped.startswith("- "):
            # We're entering or continuing a list
            flush_text()
            in_list_block = True
            item_text = lstripped[2:]  # remove leading "- "
            current_list_items.append(item_text)
            current_list_raw_lines.append(line)  # track original markdown
            continue

        # Normal paragraph text
        if in_list_block:
            # Previous block was a list; close it before starting a new paragraph
            flush_list()
        current_text_lines.append(line)

    # Flush any remaining blocks at EOF
    if in_code_block:
        flush_code()
    flush_text()
    flush_list()

    return blocks


def chapter_number_from_path(path: Path) -> int:
    """
    Given e.g. '01 明義第一.md', return 1.
    """
    stem = path.stem
    # Expect filename starting with a numeric prefix.
    number_str = stem.split()[0]
    return int(number_str)


def parse_chapter(path: Path) -> Dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    title, body_lines = parse_heading_and_body(lines)

    chapter_num = chapter_number_from_path(path)
    chapter_id = f"c{chapter_num}"

    blocks = parse_blocks(body_lines)

    data: Dict[str, Any] = {
        "id": chapter_id,
        "number": chapter_num,
        "title": title,
        "title_en": CHAPTER_TITLE_EN.get(chapter_num),
        "blocks": [asdict(b) for b in blocks],
    }
    return data


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    book_dir = root / "book"
    output_dir = root / "renderer" / "public" / "chapters"
    output_dir.mkdir(parents=True, exist_ok=True)

    chapter_files = sorted(book_dir.glob("*.md"))
    # Filter out non-chapter files (README.md, LICENSE, etc.)
    chapter_files = [f for f in chapter_files if f.stem and f.stem[0].isdigit()]

    for chapter_path in chapter_files:
        data = parse_chapter(chapter_path)
        out_path = output_dir / f"{data['id']}.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
