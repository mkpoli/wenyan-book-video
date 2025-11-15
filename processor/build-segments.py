from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import regex

from utils.cli_style import (
    INNER_DIVIDER,
    format_metadata_rows,
    format_preview_entry,
    print_warning,
)

"""
Build segment-level IPA transcript files `audio-{c}-{s}.txt` under
`renderer/public/transcripts/build` from:

  - `renderer/public/segments/c{n}.segments.json`
  - `renderer/public/transcripts/c{n}.transcripts.json`

Each entry in `c{n}.segments.json` describes a segment (e.g. "1-17") and the
ordered list of sentence IDs (e.g. ["c1-s245", "c1-s246", ...]) that belong to
that segment. For each segment, we concatenate the sentence-level IPA strings
for those sentence IDs and write the result to:

  `renderer/public/transcripts/build/audio-{segment_id}.txt`

This prepares pronunciation text, one segment per file, for the TTS engine.
The TTS engine expects a leading and trailing space around the entire IPA
string in each file, so this script ensures there is exactly one space at the
start and one space at the end (before the newline). When a converted IPA line
still contains any Chinese (Han) characters, we emit warnings so those failures
can be reviewed manually.
"""

# Any remaining Han characters indicate the conversion failed.
HAN_CHAR_PATTERN = regex.compile(r"\p{Han}")


def contains_han_characters(value: str) -> bool:
    """Return True when the provided text includes any Chinese character."""

    if not value:
        return False
    return bool(HAN_CHAR_PATTERN.search(value))


def summarize_for_preview(value: str, limit: int = 80) -> str:
    """Collapse whitespace and truncate previews for CLI readability."""

    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 1]}…"


def _segments_file_sort_key(path: Path) -> int:
    stem = path.stem  # e.g., "c1.segments"
    chapter_part = stem.split(".")[0]
    try:
        return int(chapter_part.lstrip("c"))
    except ValueError:
        return 0


def load_sentence_segments(root: Path) -> List[Dict[str, Any]]:
    """
    Load chapter segment JSON files from renderer/public/segments.
    """
    segments_dir = root / "renderer" / "public" / "segments"
    if not segments_dir.exists():
        raise SystemExit(f"Segments directory not found: {segments_dir}")

    json_files = sorted(
        segments_dir.glob("c*.segments.json"),
        key=_segments_file_sort_key,
    )
    if not json_files:
        raise SystemExit(f"No segment JSON files found in {segments_dir}")

    segments: List[Dict[str, Any]] = []
    for json_path in json_files:
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Failed to parse {json_path}: {exc}") from exc

        file_segments = data.get("segments")
        if not isinstance(file_segments, list):
            print_warning(
                "Invalid segments JSON structure",
                format_metadata_rows(
                    [
                        ("File", json_path.as_posix()),
                        ("Issue", "Missing 'segments' array"),
                    ]
                ),
            )
            continue

        chapter_id = str(data.get("chapterId") or json_path.stem.split(".")[0])
        for entry in file_segments:
            if not isinstance(entry, dict):
                continue
            normalized = {
                "id": entry.get("id"),
                "chapterId": entry.get("chapterId", chapter_id),
                "segmentIndex": entry.get("segmentIndex"),
                "sentenceIds": entry.get("sentenceIds", []),
                "isCodeBlock": bool(entry.get("isCodeBlock", False)),
            }
            segments.append(normalized)

    if not segments:
        raise SystemExit("No valid segments loaded from JSON files.")

    return segments


def load_sentence_transcripts_for_chapter(
    transcripts_dir: Path, chapter_id: str
) -> Dict[str, Dict[str, Any]]:
    """
    Load sentence-level transcripts for a chapter, keyed by sentence id
    (e.g. "c1-s245").
    """
    # Sentence-level transcripts are stored as `c{n}.transcripts.json`.
    path = transcripts_dir / f"{chapter_id}.transcripts.json"
    if not path.exists():
        raise SystemExit(f"Sentence transcripts file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    # The files use a flat mapping: { "c1-s1": { ... }, "c1-s2": { ... }, ... }
    # We keep it as-is but ensure keys are strings.
    return {str(k): v for k, v in data.items()}


def build_segment_ipa(
    segment: Dict[str, Any],
    sentence_data: Dict[str, Dict[str, Any]],
) -> str:
    """
    Given a segment record and the sentence-level data for its chapter,
    concatenate the `ipa` fields in order to produce the segment IPA text.
    """
    ipa_chunks: List[str] = []
    missing_sentences: List[str] = []
    han_sentences: List[tuple[str, str]] = []

    for sent_id in segment.get("sentenceIds", []):
        entry = sentence_data.get(sent_id)
        if entry is None:
            missing_sentences.append(sent_id)
            continue
        ipa = entry.get("ipa", "")
        if not isinstance(ipa, str) or not ipa.strip():
            missing_sentences.append(sent_id)
            continue
        ipa_clean = ipa.strip()
        if contains_han_characters(ipa_clean):
            han_sentences.append((sent_id, ipa_clean))
        ipa_chunks.append(ipa_clean)

    if missing_sentences:
        preview_rows = [
            format_preview_entry(f"#{idx:02}", "zh", sid, True)
            for idx, sid in enumerate(missing_sentences)
        ]
        metadata: List[str | object] = list(
            format_metadata_rows(
                [
                    ("Segment ID", str(segment.get("id"))),
                    ("Missing sentences", str(len(missing_sentences))),
                ]
            )
        )
        metadata.extend([INNER_DIVIDER, *preview_rows])
        print_warning("Missing IPA data", metadata)

    if han_sentences:
        preview_rows = [
            format_preview_entry(
                f"#{idx:02}",
                "zh",
                f"{sent_id}: {summarize_for_preview(sample)}",
                True,
            )
            for idx, (sent_id, sample) in enumerate(han_sentences, start=1)
        ]
        metadata = list(
            format_metadata_rows(
                [
                    ("Segment ID", str(segment.get("id"))),
                    ("Chinese text hits", str(len(han_sentences))),
                ]
            )
        )
        metadata.extend([INNER_DIVIDER, *preview_rows])
        print_warning("Chinese text detected in IPA transcripts", metadata)

    return " ".join(ipa_chunks).strip()


def reconstruct_segment_transcripts(root: Path) -> None:
    transcripts_dir = root / "renderer" / "public" / "transcripts"
    build_dir = transcripts_dir / "build"

    # Ensure the build directory exists and is clean so stale
    # transcript files don't linger between runs.
    build_dir.mkdir(parents=True, exist_ok=True)
    for stale in build_dir.glob("audio-*.txt"):
        stale.unlink()

    segments = load_sentence_segments(root)
    if not segments:
        print("No sentence segments found; nothing to do.")
        return

    # Group segments by chapter id so we can load each chapter's sentence
    # transcripts only once.
    segments_by_chapter: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for seg in segments:
        chapter_id = seg.get("chapterId")
        if not isinstance(chapter_id, str):
            continue
        segments_by_chapter[chapter_id].append(seg)

    print("Building segment-level IPA transcripts from sentence data...")

    total_written = 0
    for chapter_id, chapter_segments in sorted(
        segments_by_chapter.items(),
        key=lambda item: (
            int(item[0].lstrip("c")) if item[0].lstrip("c").isdigit() else 0
        ),
    ):
        print(f"- Chapter {chapter_id}")

        sentence_data = load_sentence_transcripts_for_chapter(
            transcripts_dir, chapter_id
        )

        # Sort segments within the chapter by numeric segmentIndex
        chapter_segments.sort(
            key=lambda s: int(s.get("segmentIndex", 0)),
        )

        for seg in chapter_segments:
            seg_id = seg.get("id")
            if not isinstance(seg_id, str):
                continue

            ipa_body = build_segment_ipa(seg, sentence_data)
            if not ipa_body:
                print_warning(
                    "No IPA constructed for segment",
                    format_metadata_rows(
                        [
                            ("Segment ID", seg_id),
                            ("Chapter ID", chapter_id),
                        ]
                    ),
                )
                continue

            # TTS engine requires exactly one leading and trailing space
            # around the content.
            ipa_text = f" {ipa_body.strip()} "
            out_path = build_dir / f"audio-{seg_id}.txt"
            out_path.write_text(ipa_text, encoding="utf-8")
            total_written += 1

            print(f"    • Wrote {out_path.relative_to(root)}")

    print(f"Done. Wrote {total_written} segment transcript files.")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    reconstruct_segment_transcripts(root)


if __name__ == "__main__":
    main()
