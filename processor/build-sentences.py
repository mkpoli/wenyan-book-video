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

    - `source` is the text used for transcription/translation.
      For prose it is markdown-cleaned; for code it preserves original
      line breaks and indentation for that sentence-like chunk.
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


def split_chinese_sentences(text: str, preserve_spaces: bool = False) -> List[str]:
    """
    Split Chinese text into sentences, with special handling for quoted text.

    This mirrors renderer's `splitChineseSentences` in
    `renderer/scripts/generate-segments.ts` so that code blocks and
    prose are segmented in a compatible way.
    """
    sentences: List[str] = []
    current_sentence: List[str] = []
    inside_quotes = False  # for 『 ... 』

    i = 0
    length = len(text)

    while i < length:
        char = text[i]

        if char == "『":
            inside_quotes = True
            current_sentence.append(char)
        elif char == "』":
            inside_quotes = False
            current_sentence.append(char)

            # Check if previous character was sentence-ending punctuation
            if i > 0:
                prev_char = text[i - 1]
                if prev_char in ("。", "！", "？"):
                    # Only split at 。』 if NOT immediately followed by another
                    # sentence-ending punctuation (e.g., don't split "。』。")
                    next_char = text[i + 1] if i + 1 < length else None
                    if next_char not in ("。", "！", "？"):
                        processed = "".join(current_sentence)
                        if not preserve_spaces:
                            processed = processed.strip()
                        if processed:
                            sentences.append(processed)
                        current_sentence = []
        elif char == "」":
            # Always include the closing quote
            current_sentence.append(char)

            # Look ahead for the next non-whitespace character.
            # If it's 「曰」, we treat this as a sentence boundary so that
            # patterns like `…耶」曰「…耶」` or `…耶」\n曰「…耶」` are split
            # between `」` and `曰`.
            j = i + 1
            next_non_ws: str | None = None
            while j < length:
                lookahead = text[j]
                if not lookahead.isspace():
                    next_non_ws = lookahead
                    break
                j += 1

            if next_non_ws == "曰":
                processed = "".join(current_sentence)
                if not preserve_spaces:
                    processed = processed.strip()
                if processed:
                    sentences.append(processed)
                current_sentence = []
        elif char in ("。", "！", "？") and not inside_quotes:
            current_sentence.append(char)
            processed = "".join(current_sentence)
            if not preserve_spaces:
                processed = processed.strip()
            if processed:
                sentences.append(processed)
            current_sentence = []
        else:
            current_sentence.append(char)

        i += 1

    # Add any remaining text as the last sentence
    processed = "".join(current_sentence)
    if not preserve_spaces:
        processed = processed.strip()
    if processed:
        sentences.append(processed)

    return sentences


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences ending with '。'.

    Sentences ending with '。' are included with the period appended.
    Trailing fragments that don't end with '。' are also included
    (e.g., "運行之。乃得" -> ["運行之。", "乃得"]).
    """
    # Fast path: no backticks, use simple splitting to preserve legacy behavior.
    if "`" not in text:
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
            else:
                # Include trailing fragment even if it doesn't end with '。'
                # (e.g., "運行之。乃得" -> ["運行之。", "乃得"])
                sentences.append(part)

        # Return all sentences (those ending with '。' and any trailing fragment)
        return [s for s in sentences if s]

    # Backtick-aware path: never break *inside* paired backticks.
    # We treat inline code spans as atomic units, but allow them to
    # carry sentence-final punctuation. For example:
    #   `曰三` `曰『問天地好在。』`者。
    # becomes:
    #   1) `曰三` `曰『問天地好在。』`
    #   2) 者。

    # First, tokenize into (segment, is_code) pairs, where code segments
    # are delimited by backticks and never split.
    tokens: List[tuple[str, bool]] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        if ch == "`":
            # Capture everything until the next backtick (or end of string).
            j = i + 1
            while j < n and text[j] != "`":
                j += 1
            if j < n:
                token = text[i : j + 1]
                i = j + 1
            else:
                token = text[i:]
                i = n
            tokens.append((token, True))
        else:
            # Plain text until the next backtick.
            j = i
            while j < n and text[j] != "`":
                j += 1
            token = text[i:j]
            if token:
                tokens.append((token, False))
            i = j

    sentences: List[str] = []
    current_parts: List[str] = []

    for segment, is_code in tokens:
        if is_code:
            # Always keep code spans intact.
            current_parts.append(segment)
            # If the code span contains '。', treat it as sentence-final
            # punctuation and end the sentence *after* this code span.
            if "。" in segment:
                sentence = "".join(current_parts).strip()
                if sentence:
                    sentences.append(sentence)
                current_parts = []
        else:
            # Plain text may contain multiple '。' characters; we split
            # on them, but never cross into code spans.
            buf: List[str] = []
            for ch in segment:
                buf.append(ch)
                if ch == "。":
                    current_parts.append("".join(buf))
                    sentence = "".join(current_parts).strip()
                    if sentence:
                        sentences.append(sentence)
                    current_parts = []
                    buf = []
            if buf:
                current_parts.append("".join(buf))

    # Add any remaining text as the last sentence.
    # Include trailing fragments even if they don't end with '。'
    # (e.g., "運行之。乃得" -> ["運行之。", "乃得"])
    tail = "".join(current_parts).strip()
    if tail:
        sentences.append(tail)

    # For the backtick-aware path, we've already enforced sentence
    # boundaries based on '。' (including those inside code spans),
    # so we only need to drop empty fragments.
    return [s for s in sentences if s]


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
            # Split code blocks into sentence-like units, preserving
            # original line breaks and indentation for each chunk.
            source_markdown = block.get("source") or ""
            # Strip fence markers but keep code as-is
            lines: List[str] = []
            for line in source_markdown.split("\n"):
                if line.strip().startswith("```"):
                    continue
                lines.append(line)
            code_text = "\n".join(lines)
            if not code_text.strip():
                continue

            # For sentence splitting, mirror the behavior used when creating
            # segments: normalize double corner quotes to 『』 so that quoted
            # runs like `曰「「問天地好在。」」` are treated as a single
            # sentence, not split in the middle.
            # We preserve all spacing and newlines.
            normalized_code_text = code_text.replace("「「", "『").replace("」」", "』")

            code_sentences = split_chinese_sentences(
                normalized_code_text, preserve_spaces=True
            )
            if not code_sentences:
                # Fallback: treat entire block as one sentence-like unit
                code_sentences = [normalized_code_text]

            for part in code_sentences:
                # Preserve exact whitespace from `part` so that code layout
                # remains visible at the sentence level.
                sentence = Sentence(
                    id=f"{chapter_id}-s{sentence_counter}",
                    chapterId=chapter_id,
                    blockId=block_id,
                    index=sentence_counter,
                    source=part,
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

    # Store canonical sentences as `c{n}.sentences.json` to avoid confusion
    # with chapter JSON (`c{n}.json`).
    output_path = output_dir / f"{chapter_id}.sentences.json"
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
