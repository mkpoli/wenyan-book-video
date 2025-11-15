from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union, cast

from processor.utils.cli_style import (
    INNER_DIVIDER,
    format_metadata_rows,
    format_preview_entry,
    print_warning,
)


def split_chinese_sentences(text: str) -> List[str]:
    """
    Split Chinese text into sentences ending with '。'.

    Mirrors the logic used in:
      - processor/migration/convert-segment-transcripts-to-sentences.py
      - processor/migration/generate_sentence_segments.py
    so that segment-level sentence counts line up with canonical
    `renderer/public/sentences/c*.sentences.json` files.
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

    # Keep all non-empty sentences, even if they do not literally end with
    # '。', because some sentences end with closing quotes.
    return [s for s in sentences if s]


def split_english_sentences(translation: str) -> List[str]:
    """
    Split an English translation into sentence-like units.

    Mirrors the logic in renderer/scripts/generate-segments.ts
    `splitEnglishSentences`, where:
      - each non-empty line is treated as one sentence unit
      - blank lines are discarded
    """
    if not translation:
        return []

    normalized = translation.replace("\r\n", "\n")
    parts = normalized.split("\n")

    sentences: List[str] = []
    for part in parts:
        line = part.strip()
        if line:
            sentences.append(line)

    return sentences


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


def convert_chapter(
    chapter_id: str,
    sentences_dir: Path,
    segments_dir: Path,
    translations_dir: Path,
    output_dir: Path,
) -> None:
    """
    Convert existing segment-based translations for one chapter into
    sentence-based translations.

    This mirrors the control flow of convert-segment-transcripts-to-sentences.py
    but is much simpler (no IPA alignment or dictionary lookups).
    """
    # Canonical sentences are stored as `c{n}.sentences.json`.
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
        return

    chapter_sentences = load_chapter_sentences(sentences_path)
    if not chapter_sentences:
        print_warning(
            "No sentences entries",
            format_metadata_rows(
                [
                    ("Sentences path", sentences_path.as_posix()),
                    ("Chapter ID", chapter_id),
                ]
            ),
        )
        return

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
        return

    # Check if any translation files exist for this chapter
    translation_files = list(translations_dir.glob(f"{chapter_num}-*.txt"))
    if not translation_files:
        print_warning(
            "No translation files found",
            format_metadata_rows(
                [
                    ("Chapter", str(chapter_num)),
                    ("Translations dir", translations_dir.as_posix()),
                ]
            ),
        )
        return

    # Find all segments for this chapter
    segment_files = sorted(
        [p for p in segments_dir.glob(f"{chapter_num}-*.txt")],
        key=natural_segment_sort_key,
    )
    if not segment_files:
        print_warning(
            "No segments available",
            format_metadata_rows(
                [
                    ("Chapter", str(chapter_num)),
                    ("Segments dir", segments_dir.as_posix()),
                ]
            ),
        )
        return

    result: Dict[str, Dict[str, str]] = {}
    sent_index = 0  # index into chapter_sentences

    for seg_path in segment_files:
        translation_path = translations_dir / f"{seg_path.stem}.txt"

        # Always advance sentence index according to Chinese sentences in this segment,
        # even if translation does not exist, to keep alignment.
        seg_text = seg_path.read_text(encoding="utf-8").strip()
        cn_sentences = split_chinese_sentences(seg_text)
        if not cn_sentences:
            if seg_text:
                cn_sentences = [seg_text]
            else:
                cn_sentences = []

        en_sentences: List[str] = []
        if translation_path.exists():
            en_text = translation_path.read_text(encoding="utf-8").strip()
            en_sentences = split_english_sentences(en_text)

            if len(en_sentences) != len(cn_sentences):
                if en_sentences and len(en_sentences) == 1:
                    # Use the same translation for all sentences in this segment.
                    en_sentences = en_sentences * len(cn_sentences)
                    print_warning(
                        "Duplicating English sentence",
                        format_metadata_rows(
                            [
                                ("Segment", seg_path.name),
                                ("Chinese sentences", str(len(cn_sentences))),
                                ("English sentences", str(len(en_sentences))),
                            ]
                        ),
                    )
                else:
                    preview_rows: List[str] = []
                    if len(cn_sentences) <= 20 and len(en_sentences) <= 20:
                        for idx in range(max(len(cn_sentences), len(en_sentences))):
                            zh_sentence = (
                                cn_sentences[idx] if idx < len(cn_sentences) else None
                            )
                            en_sentence = (
                                en_sentences[idx] if idx < len(en_sentences) else None
                            )
                            preview_rows.append(
                                format_preview_entry(
                                    f"#{idx:02}", "zh", zh_sentence, zh_sentence is None
                                ),
                            )
                            preview_rows.append(
                                format_preview_entry(
                                    f"#{idx:02}",
                                    "en",
                                    en_sentence,
                                    en_sentence is None or zh_sentence is None,
                                )
                            )

                    rows: List[Union[str, object]] = cast(
                        List[Union[str, object]],
                        format_metadata_rows(
                            [
                                ("Segment", seg_path.name),
                                ("Chinese sentences", str(len(cn_sentences))),
                                ("English sentences", str(len(en_sentences))),
                            ]
                        ),
                    )
                    if preview_rows:
                        rows.extend([INNER_DIVIDER, *preview_rows])

                    print_warning("Sentence count mismatch", rows)

        # Map this segment's sentences onto chapter sentences
        en_index = 0  # index into en_sentences for this segment
        for local_idx, cn_sentence in enumerate(cn_sentences):
            if sent_index >= len(chapter_sentences):
                print_warning(
                    "Ran out of canonical sentences",
                    format_metadata_rows(
                        [
                            ("Segment", seg_path.name),
                            ("Chapter index", str(sent_index)),
                            ("Chapter ID", chapter_id),
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

            if (
                isinstance(canonical_source, str)
                and canonical_normalized != cn_normalized
            ):
                # Simple sanity check; still proceed.
                # Only warn if the normalized versions don't match and one doesn't contain the other
                if (
                    canonical_normalized not in cn_normalized
                    and cn_normalized not in canonical_normalized
                ):
                    mismatch_rows: List[Union[str, object]] = cast(
                        List[Union[str, object]],
                        format_metadata_rows(
                            [
                                ("Segment", seg_path.name),
                                ("Chapter index", str(sent_index)),
                                ("Sentence ID", str(sent_id)),
                            ]
                        ),
                    )
                    mismatch_rows.extend(
                        [
                            INNER_DIVIDER,
                            f"canonical: {canonical_source}",
                            f"segment:   {cn_sentence}",
                        ]
                    )
                    print_warning("Sentence mismatch detected", mismatch_rows)

            translation_value = ""
            if en_sentences and en_index < len(en_sentences):
                translation_value = en_sentences[en_index]

            if sent_id and translation_value:
                entry: Dict[str, str] = {
                    "source": canonical_source,
                    "translation": translation_value,
                }
                result[sent_id] = entry

            # Advance to the next canonical and English sentence
            sent_index += 1
            if en_sentences and en_index < len(en_sentences):
                en_index += 1

    if not result:
        print_warning(
            "No sentence-level translations produced",
            format_metadata_rows([("Chapter ID", chapter_id)]),
        )
        return

    output_path = output_dir / f"{chapter_id}.translations.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"  ✅ Wrote {len(result)} sentence translations for {chapter_id} "
        f"to {output_path}"
    )


def main() -> None:
    # This script lives in processor/migration/, repo root is two levels above
    # (__file__ -> migration -> processor -> project root)
    root = Path(__file__).resolve().parents[2]
    segments_dir = root / "renderer" / "public" / "segments"
    translations_dir = root / "renderer" / "public" / "translations"
    sentences_dir = root / "renderer" / "public" / "sentences"

    if not segments_dir.exists():
        raise SystemExit(f"Segments directory not found: {segments_dir}")
    if not translations_dir.exists():
        raise SystemExit(f"Translations directory not found: {translations_dir}")
    if not sentences_dir.exists():
        raise SystemExit(f"Sentences directory not found: {sentences_dir}")

    output_dir = translations_dir  # store new files alongside existing ones

    # Determine which chapters have sentences files.
    # Files are named like "c1.sentences.json" -> chapter id "c1".
    chapter_ids = sorted(
        {p.name.split(".")[0] for p in sentences_dir.glob("c*.sentences.json")}
    )

    if not chapter_ids:
        print(f"No chapter sentences files found in {sentences_dir}")
        return

    print("Converting segment translations to sentence-based translations...")
    for chapter_id in chapter_ids:
        print(f"- Chapter {chapter_id}:")
        convert_chapter(
            chapter_id=chapter_id,
            sentences_dir=sentences_dir,
            segments_dir=segments_dir,
            translations_dir=translations_dir,
            output_dir=output_dir,
        )


if __name__ == "__main__":
    main()
