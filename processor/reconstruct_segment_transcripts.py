from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

"""
Reconstruct segment-level IPA transcript files `audio-{c}-{s}.txt` under
`renderer/public/transcripts` from:

  - `renderer/src/generated/sentence-segments.ts`
  - `renderer/public/transcripts/c{n}.sentences.json`

Each entry in `sentence-segments.ts` describes a segment (e.g. "1-17") and the
ordered list of sentence IDs (e.g. ["c1-s245", "c1-s246", ...]) which belong to
that segment. For each such segment, we concatenate the sentence-level IPA
strings for those sentence IDs and write the result to:

  `renderer/public/transcripts/audio-{segment_id}.txt`

This reproduces the segment-level `audio-{c}-{s}.txt` files based on the
sentence-level transcription data.
"""


def load_sentence_segments(root: Path) -> List[Dict[str, Any]]:
    """
    Parse `renderer/src/generated/sentence-segments.ts` and return the
    `segments` array as a list of dicts.

    The file is a small subset of TypeScript/JS; we convert the `segments`
    array literal into JSON and load it.
    """
    ts_path = root / "renderer" / "src" / "generated" / "sentence-segments.ts"
    if not ts_path.exists():
        raise SystemExit(f"Sentence segments file not found: {ts_path}")

    text = ts_path.read_text(encoding="utf-8")

    # Extract the array literal between "export const segments = [" and "] as const;"
    m = re.search(
        r"export const segments\s*=\s*\[(.*)\]\s*as const;",
        text,
        flags=re.DOTALL,
    )
    if not m:
        raise SystemExit("Could not locate `export const segments = [...] as const;`")

    array_text = "[" + m.group(1) + "]"

    # Quote object keys: id: "1-1" -> "id": "1-1"
    array_text = re.sub(r"(\s*)(\w+):", r'\1"\2":', array_text)

    # Remove trailing commas before } or ]
    array_text = re.sub(r",(\s*[}\]])", r"\1", array_text)

    try:
        segments: List[Dict[str, Any]] = json.loads(array_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Failed to parse sentence segments TS as JSON: {exc}"
        ) from exc

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
        print(
            f"  ⚠ Segment {segment.get('id')}: missing IPA for "
            f"{', '.join(missing_sentences)}; skipping those sentences."
        )

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
                print(
                    f"  ⚠ Segment {seg_id}: no IPA could be constructed; "
                    f"skipping file output."
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
