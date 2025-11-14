from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

import re


@dataclass
class Sentence:
    """
    Canonical sentence unit.

    - `source` is the cleaned Chinese text used for transcription/translation.
    - `isCode` marks sentences that originate from code blocks.
    """

    id: str
    chapterId: str
    blockId: str
    index: int  # 1-based index within the chapter
    source: str
    isCode: bool


def remove_markdown(text: str, preserve_newlines: bool = False) -> str:
    """
    Remove markdown formatting from text, preserving logical content.

    This mirrors the behavior in `segment-text.py` so that segmentation
    remains consistent with the existing pipeline.
    """
    # Convert double brackets 「「　」」 to 『 』
    text = text.replace("「「", "『")
    text = text.replace("」」", "』")

    # Remove headings (# ...)
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)

    # Remove list markers (- ...) but keep the content
    text = re.sub(r"^-\s+", "", text, flags=re.MULTILINE)

    if preserve_newlines:
        # For code blocks, preserve newlines and the exact amount of whitespace.
        return text
    else:
        # Replace multiple spaces/tabs with single space
        text = re.sub(r"[ \t]+", " ", text)
        # Replace multiple newlines with single space
        text = re.sub(r"\n+", " ", text)
        return text.strip()


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences ending with '。'.

    This matches the logic in `segment-text.py` so that segmentation
    stays compatible.
    """
    sentences: List[str] = []
    parts = text.split("。")

    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        if i < len(parts) - 1:
            sentences.append(part + "。")
        elif text.endswith("。"):
            sentences.append(part + "。")
        # If text doesn't end with '。', skip the trailing fragment.

    # Ensure only sentences that actually end with '。'
    return [s for s in sentences if s and s.endswith("。")]


def build_sentences_for_chapter(chapter_path: Path, output_dir: Path) -> None:
    """
    Read a chapter JSON from `renderer/public/chapters` and emit
    a sentence-level JSON file under `renderer/public/sentences`.
    """
    with chapter_path.open("r", encoding="utf-8") as f:
        chapter_data: Dict[str, Any] = json.load(f)

    chapter_id = chapter_data.get("id")
    chapter_num = chapter_data.get("number")
    title = chapter_data.get("title")

    if not chapter_id or chapter_num is None:
        raise ValueError(f"Chapter JSON missing id/number: {chapter_path}")

    sentences: List[Sentence] = []
    sentence_counter = 1

    blocks: List[Dict[str, Any]] = chapter_data.get("blocks", [])

    for block in blocks:
        block_id = block.get("id")
        block_type = block.get("type")

        if not block_id or not block_type:
            continue

        if block_type == "code":
            # Treat each code block as a single sentence-like unit.
            source_markdown = block.get("source") or ""
            # Strip fence markers but keep code as-is
            lines = []
            for line in source_markdown.split("\n"):
                if line.strip().startswith("```"):
                    continue
                lines.append(line)
            code_text = "\n".join(lines).strip()
            if not code_text:
                continue

            sentence = Sentence(
                id=f"{chapter_id}-s{sentence_counter}",
                chapterId=chapter_id,
                blockId=block_id,
                index=sentence_counter,
                source=code_text,
                isCode=True,
            )
            sentences.append(sentence)
            sentence_counter += 1

        elif block_type == "list":
            items = block.get("items") or []
            if not items:
                continue

            # Reconstruct markdown list paragraph to keep behavior consistent
            paragraph_markdown = "\n".join(f"- {item}" for item in items)
            text = remove_markdown(paragraph_markdown, preserve_newlines=False)
            if not text.strip():
                continue

            parts = split_sentences(text)
            if not parts:
                # Fall back to treating entire list as one sentence if no '。'
                parts = [text.strip()]

            for part in parts:
                sentence = Sentence(
                    id=f"{chapter_id}-s{sentence_counter}",
                    chapterId=chapter_id,
                    blockId=block_id,
                    index=sentence_counter,
                    source=part,
                    isCode=False,
                )
                sentences.append(sentence)
                sentence_counter += 1

        else:
            # Plain text block
            paragraph_markdown = block.get("source") or ""
            if not paragraph_markdown.strip():
                continue

            text = remove_markdown(paragraph_markdown, preserve_newlines=False)
            if not text.strip():
                continue

            parts = split_sentences(text)
            if not parts:
                # e.g. short phrases without '。'
                parts = [text.strip()]

            for part in parts:
                sentence = Sentence(
                    id=f"{chapter_id}-s{sentence_counter}",
                    chapterId=chapter_id,
                    blockId=block_id,
                    index=sentence_counter,
                    source=part,
                    isCode=False,
                )
                sentences.append(sentence)
                sentence_counter += 1

    output_data: Dict[str, Any] = {
        "chapterId": chapter_id,
        "number": chapter_num,
        "title": title,
        "sentences": [asdict(s) for s in sentences],
    }

    output_path = output_dir / f"{chapter_id}.json"
    output_path.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote sentences for {chapter_id} to {output_path}")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    chapters_dir = root / "renderer" / "public" / "chapters"
    output_dir = root / "renderer" / "public" / "sentences"

    if not chapters_dir.exists():
        raise SystemExit(f"Chapters directory not found: {chapters_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    chapter_files = sorted(chapters_dir.glob("c*.json"))
    if not chapter_files:
        print(f"No chapter JSON files found in {chapters_dir}")
        return

    for chapter_json in chapter_files:
        build_sentences_for_chapter(chapter_json, output_dir)


if __name__ == "__main__":
    main()
