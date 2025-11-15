from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

"""
Generate a structured segments mapping from existing text segments and
sentence-level JSON files.

This script reads:
  - renderer/public/sentences/c*.json   (canonical sentences with ids)
  - renderer/public/segments/{chapter}-{index}.txt
  - renderer/public/segments/{chapter}.json (isCodeBlock metadata, if present)

and writes:
  - renderer/src/generated/sentence-segments.ts

The output format is a TypeScript file exporting:

  export type SentenceSegment = {
    id: string;             // e.g. "1-17"
    chapterId: string;      // e.g. "c1"
    segmentIndex: number;   // e.g. 17
    sentenceIds: string[];  // e.g. ["c1-s245", "c1-s246"]
    isCodeBlock: boolean;
  };

  export const segments = [...] as const;
  export type Segment = (typeof segments)[number];
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
    sentences_path = sentences_dir / f"{chapter_id}.json"
    if not sentences_path.exists():
        print(f"  ⚠ No sentences file found for {chapter_id}, skipping.")
        return []

    chapter_sentences = load_chapter_sentences(sentences_path)
    if not chapter_sentences:
        print(f"  ⚠ No sentences entries in {sentences_path}, skipping.")
        return []

    # Determine numeric chapter number from chapter_id like "c1"
    try:
        chapter_num = int(chapter_id.lstrip("c"))
    except ValueError:
        print(f"  ⚠ Invalid chapter id format: {chapter_id}, skipping.")
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
        print(f"  ⚠ No segment files found for chapter {chapter_num}, skipping.")
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
                print(
                    f"  ⚠ Ran out of chapter sentences while processing {seg_path.name}; "
                    f"remaining segment content will be ignored."
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


def generate_sentence_segments_ts(root: Path) -> None:
    sentences_dir = root / "renderer" / "public" / "sentences"
    segments_dir = root / "renderer" / "public" / "segments"
    output_dir = root / "renderer" / "src" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sentence-segments.ts"

    # Sort chapters in numeric order by chapter number (c1, c2, ..., c10)
    chapter_files = list(sentences_dir.glob("c*.json"))
    chapter_files.sort(
        key=lambda p: int(p.stem.lstrip("c")) if p.stem.lstrip("c").isdigit() else 0
    )
    if not chapter_files:
        raise SystemExit(f"No sentence JSON files found in {sentences_dir}")

    all_segments: List[Dict[str, Any]] = []

    print("Building sentence segments from existing segments and sentences...")
    for sentences_path in chapter_files:
        chapter_id = sentences_path.stem  # e.g. "c1"
        print(f"- Chapter {chapter_id}")
        chapter_segments = build_sentence_segments_for_chapter(
            chapter_id, sentences_dir, segments_dir
        )
        all_segments.extend(chapter_segments)

    # Sort by (chapter number, segment index) for stable output
    def sort_key(entry: Dict[str, Any]) -> Tuple[int, int]:
        cid = entry.get("chapterId", "")
        try:
            cnum = int(str(cid).lstrip("c"))
        except ValueError:
            cnum = 0
        return (cnum, int(entry.get("segmentIndex", 0)))

    all_segments.sort(key=sort_key)

    # Emit TypeScript
    lines: List[str] = []
    lines.append(
        "// Auto-generated by processor/migration/generate_sentence_segments.py. "
        "Do not edit manually."
    )
    lines.append("")
    lines.append("export type SentenceSegment = {")
    lines.append("  id: string;")
    lines.append("  chapterId: string;")
    lines.append("  segmentIndex: number;")
    lines.append("  sentenceIds: string[];")
    lines.append("  isCodeBlock: boolean;")
    lines.append("};")
    lines.append("")
    lines.append("export const segments = [")

    for seg in all_segments:
        seg_id = seg["id"]
        chapter_id = seg["chapterId"]
        segment_index = seg["segmentIndex"]
        sentence_ids: List[str] = seg["sentenceIds"]
        is_code_block = seg["isCodeBlock"]

        lines.append("  {")
        lines.append(f'    id: "{seg_id}",')
        lines.append(f'    chapterId: "{chapter_id}",')
        lines.append(f"    segmentIndex: {segment_index},")

        if sentence_ids:
            ids_literal = ", ".join(f'"{sid}"' for sid in sentence_ids)
            lines.append(f"    sentenceIds: [{ids_literal}],")
        else:
            lines.append("    sentenceIds: [],")

        lines.append(f"    isCodeBlock: {str(is_code_block).lower()},")
        lines.append("  },")

    lines.append("] as const;")
    lines.append("export type Segment = (typeof segments)[number];")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(all_segments)} segments to {output_path}")


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    generate_sentence_segments_ts(root)


if __name__ == "__main__":
    main()
