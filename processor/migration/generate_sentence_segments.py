from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:  # Support both `-m processor.migration...` and direct script execution
    from ..utils.cli_style import format_metadata_rows, print_warning
except ImportError:
    if __package__ in (None, "", "__main__"):
        import sys

        current_dir = Path(__file__).resolve().parent
        package_root = current_dir.parent
        if str(package_root) not in sys.path:
            sys.path.insert(0, str(package_root))
        from utils.cli_style import format_metadata_rows, print_warning
    else:  # pragma: no cover - unexpected import failure
        raise

"""
Generate chapter-scoped segment mapping files from existing text segments and
sentence-level JSON files.

This script reads:
  - renderer/public/sentences/c*.json   (canonical sentences with ids)
  - renderer/public/segments/{chapter}-{index}.txt
  - renderer/public/segments/{chapter}.json (isCodeBlock metadata, if present)

and writes, per chapter:
  - renderer/public/segments/c{n}.segments.json

Each JSON file contains:
{
  "chapterId": "c1",
  "chapterNumber": 1,
  "segments": [
    {
      "id": "1-17",
      "chapterId": "c1",
      "segmentIndex": 17,
      "sentenceIds": ["c1-s245", "c1-s246"],
      "isCodeBlock": false
    }
  ]
}
"""


def split_chinese_sentences(text: str) -> List[str]:
    """
    Split Chinese text into sentences ending with '。', with special
    handling for quoted text and corner quotes, mirroring the logic
    used in the migration script.
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
                        processed = "".join(current_sentence).strip()
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
                processed = "".join(current_sentence).strip()
                if processed:
                    sentences.append(processed)
                current_sentence = []
        elif char in ("。", "！", "？") and not inside_quotes:
            current_sentence.append(char)
            processed = "".join(current_sentence).strip()
            if processed:
                sentences.append(processed)
            current_sentence = []
        else:
            current_sentence.append(char)

        i += 1

    # Add any remaining text as the last sentence
    processed = "".join(current_sentence).strip()
    if processed:
        sentences.append(processed)

    # For our purposes we keep all non-empty sentences, even if they do not
    # literally end with '。', because some sentences end with closing quotes.
    return [s for s in sentences if s]


def natural_segment_sort_key(path: Path) -> Tuple[int, int]:
    """
    Sort key for segment files like '1-2.txt' -> (1, 2).
    """
    name = path.stem  # "1-2"
    parts = name.split("-")
    if len(parts) != 2:
        return (0, 0)
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return (0, 0)


def load_chapter_sentences(sentences_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(sentences_path.read_text(encoding="utf-8"))
    return list(data.get("sentences", []))


def normalize_for_comparison(text: str) -> str:
    """
    Normalize Chinese sentences for comparison:
      - remove backticks (inline code markers)
      - collapse whitespace
    """
    # Remove backticks (used in code/inline sentences)
    text = text.replace("`", "")

    import re

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_sentence_segments_for_chapter(
    chapter_id: str,
    sentences_dir: Path,
    segments_dir: Path,
) -> List[Dict[str, Any]]:
    """
    Compute the mapping from segment id (e.g. '1-17') to sentence ids
    (e.g. ['c1-s245', 'c1-s246']) for one chapter.
    """
    sentences_path = sentences_dir / f"{chapter_id}.sentences.json"
    if not sentences_path.exists():
        print_warning(
            "Missing sentences file",
            format_metadata_rows(
                [
                    ("Chapter ID", chapter_id),
                    ("Sentences path", sentences_path.as_posix()),
                ]
            ),
        )
        return []

    chapter_sentences = load_chapter_sentences(sentences_path)
    if not chapter_sentences:
        print_warning(
            "No sentences entries",
            format_metadata_rows(
                [
                    ("Chapter ID", chapter_id),
                    ("Sentences path", sentences_path.as_posix()),
                ]
            ),
        )
        return []

    # Determine numeric chapter number from chapter_id like "c1"
    try:
        chapter_num = int(chapter_id.lstrip("c"))
    except ValueError:
        print_warning(
            "Invalid chapter identifier",
            format_metadata_rows(
                [
                    ("Chapter ID", chapter_id),
                    ("Sentences path", sentences_path.as_posix()),
                ]
            ),
        )
        return []

    # Load code-block metadata if present (e.g. 3.json, 4.json)
    is_code_meta: Dict[str, Dict[str, Any]] = {}
    meta_path = segments_dir / f"{chapter_num}.json"
    if meta_path.exists():
        is_code_meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Find all segments for this chapter
    segment_files = sorted(
        [p for p in segments_dir.glob(f"{chapter_num}-*.txt")],
        key=natural_segment_sort_key,
    )
    if not segment_files:
        print_warning(
            "No segment files found",
            format_metadata_rows(
                [
                    ("Chapter", str(chapter_num)),
                    ("Segments dir", segments_dir.as_posix()),
                ]
            ),
        )
        return []

    results: List[Dict[str, Any]] = []
    sent_index = 0  # index into chapter_sentences

    for seg_path in segment_files:
        seg_id = seg_path.stem  # e.g. "1-17"
        seg_text = seg_path.read_text(encoding="utf-8").strip()
        cn_sentences = split_chinese_sentences(seg_text)
        if not cn_sentences:
            if seg_text:
                cn_sentences = [seg_text]
            else:
                cn_sentences = []

        sentence_ids_for_segment: List[str] = []

        for cn_sentence in cn_sentences:
            if sent_index >= len(chapter_sentences):
                total_canonical = len(chapter_sentences)
                preview = (
                    cn_sentence.strip()
                    if len(cn_sentence) <= 60
                    else cn_sentence.strip()[:57] + "..."
                )
                print_warning(
                    "Ran out of canonical sentences",
                    format_metadata_rows(
                        [
                            ("Segment", seg_path.name),
                            ("Chapter ID", chapter_id),
                            ("Segment sentence #", str(len(sentence_ids_for_segment) + 1)),
                            ("Segment sentence preview", preview or "<empty>"),
                            ("Canonical sentences in chapter", str(total_canonical)),
                            ("Sentences already matched", str(sent_index)),
                        ]
                    ),
                )
                break

            s_entry = chapter_sentences[sent_index]
            sent_id = s_entry.get("id")
            canonical_source = s_entry.get("source", "")

            canonical_normalized = (
                normalize_for_comparison(canonical_source)
                if isinstance(canonical_source, str)
                else ""
            )
            cn_normalized = normalize_for_comparison(cn_sentence)

            # Check if segment sentence spans multiple canonical sentences
            # (e.g., "曰三 曰『問天地好在。』者。" contains both c1-s245 and c1-s246)
            spans_multiple = False
            if (
                canonical_normalized
                and cn_normalized
                and canonical_normalized in cn_normalized
            ):
                # Check if there's a next canonical sentence that also fits
                # in the segment sentence
                if sent_index + 1 < len(chapter_sentences):
                    next_canonical = chapter_sentences[sent_index + 1].get("source", "")
                    next_normalized = normalize_for_comparison(next_canonical)
                    if next_normalized:
                        combined = canonical_normalized + " " + next_normalized
                        if combined.replace(" ", "") in cn_normalized.replace(" ", ""):
                            spans_multiple = True

            if spans_multiple:
                # First canonical sentence
                if sent_id:
                    sentence_ids_for_segment.append(sent_id)
                sent_index += 1

                # Second canonical sentence
                if sent_index < len(chapter_sentences):
                    next_entry = chapter_sentences[sent_index]
                    next_sent_id = next_entry.get("id")
                    if next_sent_id:
                        sentence_ids_for_segment.append(next_sent_id)
                    sent_index += 1

                # This segment sentence has been fully accounted for.
                continue

            # Normal single-sentence mapping
            if sent_id:
                sentence_ids_for_segment.append(sent_id)
            sent_index += 1

        # Derive numeric segment index from id like "1-17"
        try:
            _, seg_index_str = seg_id.split("-", 1)
            segment_index = int(seg_index_str)
        except ValueError:
            segment_index = 0

        # isCodeBlock from metadata if present
        meta_entry = is_code_meta.get(seg_id) or {}
        is_code_block = bool(meta_entry.get("isCodeBlock", False))

        segment_record = {
            "id": seg_id,
            "chapterId": chapter_id,
            "segmentIndex": segment_index,
            "sentenceIds": sentence_ids_for_segment,
            "isCodeBlock": is_code_block,
        }

        results.append(segment_record)

    return results


def write_chapter_segments_json(
    output_dir: Path,
    chapter_id: str,
    chapter_num: int,
    segments: List[Dict[str, Any]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{chapter_id}.segments.json"
    payload = {
        "chapterId": chapter_id,
        "chapterNumber": chapter_num,
        "segments": segments,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def generate_sentence_segments_json(root: Path) -> None:
    sentences_dir = root / "renderer" / "public" / "sentences"
    segments_dir = root / "renderer" / "public" / "segments"
    if not segments_dir.exists():
        raise SystemExit(f"Segments directory not found: {segments_dir}")

    # Sort chapters in numeric order by chapter number (c1, c2, ...),
    # using the canonical sentence files `c{n}.sentences.json`.
    chapter_files = list(sentences_dir.glob("c*.sentences.json"))
    chapter_files.sort(
        key=lambda p: (
            int(p.stem.split(".")[0].lstrip("c"))
            if p.stem.split(".")[0].lstrip("c").isdigit()
            else 0
        )
    )
    if not chapter_files:
        raise SystemExit(f"No sentence JSON files found in {sentences_dir}")

    total_segments = 0

    print("Building sentence segments from existing segments and sentences...")
    for sentences_path in chapter_files:
        # Derive chapter id like "c1" from "c1.sentences"
        chapter_id = sentences_path.stem.split(".")[0]
        print(f"- Chapter {chapter_id}")
        chapter_segments = build_sentence_segments_for_chapter(
            chapter_id, sentences_dir, segments_dir
        )
        if not chapter_segments:
            print_warning(
                "No sentence segments generated",
                format_metadata_rows(
                    [
                        ("Chapter ID", chapter_id),
                        ("Sentences path", sentences_path.as_posix()),
                        ("Segments dir", segments_dir.as_posix()),
                    ]
                ),
            )
            continue

        try:
            chapter_num = int(chapter_id.lstrip("c"))
        except ValueError:
            chapter_num = 0

        output_path = write_chapter_segments_json(
            segments_dir, chapter_id, chapter_num, chapter_segments
        )
        total_segments += len(chapter_segments)
        print(f"  • Wrote {len(chapter_segments)} segments → {output_path}")

    print(
        f"Done. Wrote {total_segments} segments across {len(chapter_files)} chapter files."
    )


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    generate_sentence_segments_json(root)


if __name__ == "__main__":
    main()
