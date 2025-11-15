from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from processor.utils.cli_style import (
    INNER_DIVIDER,
    format_metadata_rows,
    format_preview_entry,
    print_warning,
)

"""
Reconstruct segment-level IPA transcript files `audio-{c}-{s}.txt` under
`renderer/public/transcripts` from:

  - `renderer/public/segments/c{n}.segments.json`
  - `renderer/public/transcripts/c{n}.sentences.json`

Each entry in `c{n}.segments.json` describes a segment (e.g. "1-17") and the
ordered list of sentence IDs (e.g. ["c1-s245", "c1-s246", ...]) which belong to
that segment. For each such segment, we concatenate the sentence-level IPA
strings for those sentence IDs and write the result to:

  `renderer/public/transcripts/audio-{segment_id}.txt`

This reproduces the segment-level `audio-{c}-{s}.txt` files based on the
sentence-level transcription data.
"""


def _segments_file_sort_key(path: Path) -> int:
    stem = path.stem
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
    path = transcripts_dir / f"{chapter_id}.sentences.json"
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

    for sent_id in segment.get("sentenceIds", []):
        entry = sentence_data.get(sent_id)
        if entry is None:
            missing_sentences.append(sent_id)
            continue
        ipa = entry.get("ipa", "")
        if not isinstance(ipa, str) or not ipa.strip():
            missing_sentences.append(sent_id)
            continue
        ipa_chunks.append(ipa.strip())

    if missing_sentences:
        preview_rows = [
            format_preview_entry(f"#{idx:02}", "zh", sent_id, True)
            for idx, sent_id in enumerate(missing_sentences)
        ]
        rows: List[str | object] = list(
            format_metadata_rows(
                [
                    ("Segment ID", str(segment.get("id"))),
                    ("Missing sentences", str(len(missing_sentences))),
                ]
            )
        )
        rows.extend([INNER_DIVIDER, *preview_rows])
        print_warning("Missing IPA data", rows)

    return " ".join(ipa_chunks).strip()


def reconstruct_segment_transcripts(root: Path) -> None:
    transcripts_dir = root / "renderer" / "public" / "transcripts"

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

    print("Reconstructing segment-level IPA transcripts from sentence data...")

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

            ipa_text = build_segment_ipa(seg, sentence_data)
            if not ipa_text:
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

            out_path = transcripts_dir / f"audio-{seg_id}.txt"
            out_path.write_text(ipa_text + "\n", encoding="utf-8")
            total_written += 1

            print(f"    • Wrote {out_path.relative_to(root)}")

    print(f"Done. Wrote {total_written} segment transcript files.")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    reconstruct_segment_transcripts(root)


if __name__ == "__main__":
    main()
