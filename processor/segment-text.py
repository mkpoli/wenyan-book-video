from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.cli_style import format_metadata_rows, print_warning


@dataclass
class RawSegment:
    id: str
    segment_index: int
    text: str
    is_code_block: bool
    block_id: str | None = None


@dataclass
class ChapterSegments:
    chapter_id: str
    chapter_num: int
    segments: list[RawSegment]


@dataclass
class SentenceSegmentRecord:
    id: str
    chapter_id: str
    chapter_num: int
    segment_index: int
    sentence_ids: list[str]
    is_code_block: bool


def serialize_segment_record(record: SentenceSegmentRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "chapterId": record.chapter_id,
        "segmentIndex": record.segment_index,
        "sentenceIds": record.sentence_ids,
        "isCodeBlock": record.is_code_block,
    }


def visible_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def remove_markdown(text: str, preserve_newlines: bool = False) -> str:
    text = text.replace("「「", "『")
    text = text.replace("」」", "』")

    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^-\s+", "", text, flags=re.MULTILINE)

    if preserve_newlines:
        return text

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    parts = text.split("。")

    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        if i < len(parts) - 1 or text.endswith("。"):
            sentences.append(part + "。")

    return [s for s in sentences if s.endswith("。")]


def create_segments(
    sentences: list[str], min_chars: int = 85, max_chars: int = 95
) -> list[str]:
    segments: list[str] = []
    current_segment: list[str] = []
    current_length = 0
    i = 0

    while i < len(sentences):
        sentence = sentences[i]
        sentence_length = visible_length(sentence)

        if not current_segment:
            current_segment.append(sentence)
            current_length = sentence_length
            i += 1
            continue

        if current_length + sentence_length > max_chars:
            if current_length >= min_chars:
                segments.append("".join(current_segment))
                current_segment = []
                current_length = 0
            else:
                current_segment.append(sentence)
                current_length += sentence_length
                segments.append("".join(current_segment))
                current_segment = []
                current_length = 0
                i += 1
        else:
            current_segment.append(sentence)
            current_length += sentence_length
            i += 1

            if current_length >= min_chars and i < len(sentences):
                next_length = visible_length(sentences[i])
                if current_length + next_length > max_chars:
                    segments.append("".join(current_segment))
                    current_segment = []
                    current_length = 0

    if current_segment:
        segments.append("".join(current_segment))

    return segments


def segment_code_block(source: str) -> list[str]:
    lines = []
    for line in source.splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(line)

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        return []

    code_text = "\n".join(lines)
    if len(code_text) <= 95:
        return [code_text]

    segments: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    for line in lines:
        line_length = len(line) + 1
        if current_length + line_length > 95 and current_lines:
            segments.append("\n".join(current_lines))
            current_lines = [line]
            current_length = line_length
        else:
            current_lines.append(line)
            current_length += line_length

    if current_lines:
        segments.append("\n".join(current_lines))

    return segments


def segment_chapter(chapter_path: Path) -> ChapterSegments:
    with chapter_path.open("r", encoding="utf-8") as f:
        chapter_data = json.load(f)

    chapter_num = chapter_data.get("number")
    if chapter_num is None:
        chapter_num = int(chapter_path.stem.lstrip("c"))
    chapter_num = int(chapter_num)

    chapter_id = chapter_data.get("id") or f"c{chapter_num}"
    blocks = chapter_data.get("blocks", [])

    segments: list[RawSegment] = []
    segment_counter = 1

    for block in blocks:
        block_id = block.get("id")
        block_type = block.get("type")
        is_code_block = block_type == "code"
        paragraph_segments: list[str] = []

        if block_type == "code":
            paragraph_segments = segment_code_block(block.get("source") or "")
        elif block_type == "list":
            items = block.get("items") or []
            if not items:
                continue
            paragraph_markdown = "\n".join(f"- {item}" for item in items)
            text = remove_markdown(paragraph_markdown, preserve_newlines=False)
            if not text.strip():
                continue
            sentences = split_sentences(text)
            if sentences:
                paragraph_segments = create_segments(sentences)
            elif text.strip():
                paragraph_segments = [text.strip()]
        else:
            source = block.get("source") or ""
            if not source.strip():
                continue
            text = remove_markdown(source, preserve_newlines=False)
            if not text.strip():
                continue
            sentences = split_sentences(text)
            if sentences:
                paragraph_segments = create_segments(sentences)
            elif text.strip():
                paragraph_segments = [text.strip()]

        for segment_text in paragraph_segments:
            cleaned = segment_text.strip()
            if not cleaned:
                continue
            segment_id = f"{chapter_num}-{segment_counter}"
            segments.append(
                RawSegment(
                    id=segment_id,
                    segment_index=segment_counter,
                    text=cleaned,
                    is_code_block=is_code_block,
                    block_id=block_id,
                )
            )
            segment_counter += 1

    return ChapterSegments(
        chapter_id=chapter_id, chapter_num=chapter_num, segments=segments
    )


def split_chinese_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    current_sentence: list[str] = []
    inside_quotes = False

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
            if i > 0:
                prev_char = text[i - 1]
                if prev_char in ("。", "！", "？"):
                    next_char = text[i + 1] if i + 1 < length else None
                    if next_char not in ("。", "！", "？"):
                        processed = "".join(current_sentence).strip()
                        if processed:
                            sentences.append(processed)
                        current_sentence = []
        elif char == "」":
            current_sentence.append(char)
            j = i + 1
            next_non_ws = None
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
        elif char == "\n" and not inside_quotes:
            # Treat consecutive newlines as a single delimiter.
            # Collect all consecutive newlines.
            newlines = [char]
            j = i + 1
            while j < length and text[j] == "\n":
                newlines.append(text[j])
                j += 1
            
            processed = "".join(current_sentence).strip()
            if processed:
                sentences.append(processed)
            current_sentence = newlines
            i = j - 1  # Will be incremented at end of loop
        elif char in ("。", "！", "？") and not inside_quotes:
            current_sentence.append(char)
            processed = "".join(current_sentence).strip()
            if processed:
                sentences.append(processed)
            current_sentence = []
        else:
            current_sentence.append(char)

        i += 1

    processed = "".join(current_sentence).strip()
    if processed:
        sentences.append(processed)

    return [s for s in sentences if s]


def normalize_for_comparison(text: str) -> str:
    text = text.replace("`", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_chapter_sentences(
    sentences_dir: Path, chapter_id: str
) -> list[dict[str, Any]]:
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

    with sentences_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("sentences", []))


def map_segments_to_sentence_ids(
    chapter_segments: ChapterSegments, chapter_sentences: list[dict[str, Any]]
) -> list[SentenceSegmentRecord]:
    if not chapter_sentences:
        return []

    sent_index = 0
    results: list[SentenceSegmentRecord] = []

    for segment in chapter_segments.segments:
        segment_text = segment.text.strip()
        cn_sentences = split_chinese_sentences(segment_text)
        if not cn_sentences and segment_text:
            cn_sentences = [segment_text]
        segment_block_id = getattr(segment, "block_id", None)

        sentence_ids_for_segment: list[str] = []

        for cn_sentence in cn_sentences:
            if sent_index >= len(chapter_sentences):
                print_warning(
                    "Ran out of canonical sentences",
                    format_metadata_rows(
                        [
                            ("Segment ID", segment.id),
                            ("Chapter ID", chapter_segments.chapter_id),
                            ("Sentence index", str(sent_index)),
                        ]
                    ),
                )
                break

            entry = chapter_sentences[sent_index]
            entry_block_id = entry.get("blockId")

            if (
                segment_block_id
                and entry_block_id
                and entry_block_id != segment_block_id
            ):
                if sentence_ids_for_segment:
                    break

                match_index = next(
                    (
                        idx
                        for idx in range(sent_index, len(chapter_sentences))
                        if chapter_sentences[idx].get("blockId") == segment_block_id
                    ),
                    None,
                )
                if match_index is None:
                    print_warning(
                        "Could not locate sentences for block",
                        format_metadata_rows(
                            [
                                ("Segment ID", segment.id),
                                ("Block ID", str(segment_block_id)),
                                ("Chapter ID", chapter_segments.chapter_id),
                            ]
                        ),
                    )
                    break

                sent_index = match_index
                entry = chapter_sentences[sent_index]
                entry_block_id = entry.get("blockId")

            sent_id = entry.get("id")
            canonical_source = entry.get("source", "")

            canonical_normalized = (
                normalize_for_comparison(canonical_source)
                if isinstance(canonical_source, str)
                else ""
            )
            cn_normalized = normalize_for_comparison(cn_sentence)

            spans_multiple = False
            if (
                canonical_normalized
                and cn_normalized
                and canonical_normalized in cn_normalized
            ):
                if sent_index + 1 < len(chapter_sentences):
                    next_source = chapter_sentences[sent_index + 1].get("source", "")
                    next_normalized = normalize_for_comparison(next_source)
                    if next_normalized:
                        combined = canonical_normalized + " " + next_normalized
                        if combined.replace(" ", "") in cn_normalized.replace(" ", ""):
                            spans_multiple = True

            if spans_multiple:
                if sent_id:
                    sentence_ids_for_segment.append(sent_id)
                sent_index += 1
                if sent_index < len(chapter_sentences):
                    next_entry = chapter_sentences[sent_index]
                    next_id = next_entry.get("id")
                    if next_id:
                        sentence_ids_for_segment.append(next_id)
                    sent_index += 1
                continue

            if sent_id:
                sentence_ids_for_segment.append(sent_id)
            sent_index += 1

        # Only include segments that have at least one sentence ID
        if sentence_ids_for_segment:
            results.append(
                SentenceSegmentRecord(
                    id=segment.id,
                    chapter_id=chapter_segments.chapter_id,
                    chapter_num=chapter_segments.chapter_num,
                    segment_index=segment.segment_index,
                    sentence_ids=sentence_ids_for_segment,
                    is_code_block=segment.is_code_block,
                )
            )
        else:
            print_warning(
                "Skipping segment with no sentence IDs",
                format_metadata_rows(
                    [
                        ("Segment ID", segment.id),
                        ("Chapter ID", chapter_segments.chapter_id),
                        (
                            "Segment text preview",
                            (
                                segment_text[:50] + "..."
                                if len(segment_text) > 50
                                else segment_text
                            ),
                        ),
                    ]
                ),
            )

    # Renumber segments to have sequential indices
    for idx, record in enumerate(results, start=1):
        record.segment_index = idx
        record.id = f"{chapter_segments.chapter_num}-{idx}"

    return results


def write_chapter_segments_json(
    output_dir: Path,
    chapter: ChapterSegments,
    segments: list[SentenceSegmentRecord],
    *,
    overwrite: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{chapter.chapter_id}.segments.json"
    payload = {
        "chapterId": chapter.chapter_id,
        "chapterNumber": chapter.chapter_num,
        "segments": [serialize_segment_record(seg) for seg in segments],
    }
    if output_path.exists() and not overwrite:
        print_warning(
            "Segment JSON already exists",
            format_metadata_rows(
                [
                    ("Chapter ID", chapter.chapter_id),
                    ("Output path", output_path.as_posix()),
                ]
            ),
        )
        return output_path

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Generate renderer segments JSON.")
    parser.add_argument(
        "chapter_number",
        nargs="?",
        type=int,
        help="Only process the specified chapter number (e.g., 5 for c5).",
    )
    args = parser.parse_args(argv)

    target_chapter = args.chapter_number

    root = Path(__file__).resolve().parents[1]
    chapters_dir = root / "renderer" / "public" / "chapters"
    sentences_dir = root / "renderer" / "public" / "sentences"
    segments_output_dir = root / "renderer" / "public" / "segments"

    chapter_files = sorted(
        chapters_dir.glob("c*.json"), key=lambda p: int(p.stem.lstrip("c"))
    )
    if not chapter_files:
        raise SystemExit(f"No chapter JSON files found in {chapters_dir}")

    if target_chapter is not None:
        chapter_files = [
            p for p in chapter_files if int(p.stem.lstrip("c")) == target_chapter
        ]
        if not chapter_files:
            raise SystemExit(
                f"Could not find chapter JSON for chapter {target_chapter} in {chapters_dir}"
            )

    total_segments = 0

    for chapter_file in chapter_files:
        chapter_segments = segment_chapter(chapter_file)
        chapter_id = chapter_segments.chapter_id
        sentences = load_chapter_sentences(sentences_dir, chapter_id)
        mapped = map_segments_to_sentence_ids(chapter_segments, sentences)
        if not mapped:
            print_warning(
                "No sentence mappings produced",
                format_metadata_rows(
                    [
                        ("Chapter file", chapter_file.name),
                        ("Chapter ID", chapter_id),
                    ]
                ),
            )
            continue

        output_path = write_chapter_segments_json(
            segments_output_dir, chapter_segments, mapped
        )
        total_segments += len(mapped)
        print(
            f"Processed {chapter_file.name}: {len(chapter_segments.segments)} segments → {len(mapped)} SentenceSegment records → {output_path}"
        )

    print(
        f"Wrote {total_segments} sentence segments across {len(chapter_files)} chapter files."
    )


if __name__ == "__main__":
    main()
