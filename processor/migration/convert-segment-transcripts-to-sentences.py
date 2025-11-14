from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from cinix_to_tupa import convert_cinix_to_tupa


def split_chinese_sentences(text: str) -> List[str]:
    """
    Split Chinese text into sentences ending with '。'.
    Mirrors the logic used in segment-text and build-sentences.
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

    return [s for s in sentences if s and s.endswith("。")]


def split_ipa_sentences(ipa: str) -> List[str]:
    """
    Split an IPA transcription string into sentence-like units using '.' as marker.

    transcribe.py produces text like:
      " pèn ... . ... . "
    We group everything up to and including each '.' as one sentence.
    """
    ipa = ipa.strip()
    if not ipa:
        return []

    sentences: List[str] = []
    current: List[str] = []

    for ch in ipa:
        current.append(ch)
        if ch == ".":
            s = "".join(current).strip()
            if s:
                sentences.append(s)
            current = []

    # Any trailing content without a '.' becomes a final sentence
    tail = "".join(current).strip()
    if tail:
        sentences.append(tail)

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


def convert_chapter(
    chapter_id: str,
    sentences_dir: Path,
    segments_dir: Path,
    transcripts_dir: Path,
    output_dir: Path,
) -> None:
    """
    Convert existing segment-based transcripts for one chapter into
    sentence-based transcripts.
    """
    sentences_path = sentences_dir / f"{chapter_id}.json"
    if not sentences_path.exists():
        print(f"  ⚠ No sentences file found for {chapter_id}, skipping.")
        return

    chapter_sentences = load_chapter_sentences(sentences_path)
    if not chapter_sentences:
        print(f"  ⚠ No sentences entries in {sentences_path}, skipping.")
        return

    # Determine numeric chapter number from chapter_id like "c1"
    try:
        chapter_num = int(chapter_id.lstrip("c"))
    except ValueError:
        print(f"  ⚠ Invalid chapter id format: {chapter_id}, skipping.")
        return

    # Find all segments for this chapter
    segment_files = sorted(
        [p for p in segments_dir.glob(f"{chapter_num}-*.txt")],
        key=natural_segment_sort_key,
    )
    if not segment_files:
        print(f"  ⚠ No segment files found for chapter {chapter_num}, skipping.")
        return

    result: Dict[str, Dict[str, str]] = {}
    sent_index = 0  # index into chapter_sentences

    for seg_path in segment_files:
        transcript_path = transcripts_dir / f"audio-{seg_path.stem}.txt"

        # Always advance sentence index according to Chinese sentences in this segment,
        # even if transcript does not exist, to keep alignment.
        seg_text = seg_path.read_text(encoding="utf-8").strip()
        cn_sentences = split_chinese_sentences(seg_text)
        if not cn_sentences:
            if seg_text:
                cn_sentences = [seg_text]
            else:
                cn_sentences = []

        ipa_sentences: List[str] = []
        if transcript_path.exists():
            ipa_text = transcript_path.read_text(encoding="utf-8").strip()
            ipa_sentences = split_ipa_sentences(ipa_text)

            if len(ipa_sentences) != len(cn_sentences):
                # Fallbacks:
                if ipa_sentences and len(ipa_sentences) == 1:
                    # Use the same IPA for all sentences in this segment.
                    ipa_sentences = ipa_sentences * len(cn_sentences)
                    print(
                        f"  ⚠ Segment {seg_path.name}: "
                        f"1 IPA sentence vs {len(cn_sentences)} Chinese sentences, "
                        f"duplicating IPA."
                    )
                else:
                    print(
                        f"  ⚠ Segment {seg_path.name}: "
                        f"{len(ipa_sentences)} IPA sentences vs {len(cn_sentences)} Chinese sentences, "
                        f"will pair up to min length and discard extras."
                    )

        # Map this segment's sentences onto chapter sentences
        for local_idx, cn_sentence in enumerate(cn_sentences):
            if sent_index >= len(chapter_sentences):
                print(
                    f"  ⚠ Ran out of chapter sentences while processing {seg_path.name}; "
                    f"remaining segment content will be ignored."
                )
                break

            s_entry = chapter_sentences[sent_index]
            sent_id = s_entry.get("id")
            canonical_source = s_entry.get("source", "")

            if isinstance(canonical_source, str) and canonical_source != cn_sentence:
                # Simple sanity check; still proceed.
                # Strip whitespace for comparison to reduce false positives.
                if canonical_source.strip() != cn_sentence.strip():
                    print(
                        f"  ⚠ Sentence mismatch in {seg_path.name} at chapter index {sent_index}:"
                        f"\n     canonical: {canonical_source}"
                        f"\n     segment:   {cn_sentence}"
                    )

            ipa_value = ""
            if ipa_sentences and local_idx < len(ipa_sentences):
                ipa_value = ipa_sentences[local_idx]

            if sent_id and ipa_value:
                result[sent_id] = {
                    "source": canonical_source,
                    "ipa": ipa_value,
                    "tupa": convert_cinix_to_tupa(ipa_value),
                }

            sent_index += 1

    if not result:
        print(f"  ⚠ No sentence-level transcripts produced for {chapter_id}.")
        return

    output_path = output_dir / f"{chapter_id}.sentences.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"  ✅ Wrote {len(result)} sentence transcripts for {chapter_id} "
        f"to {output_path}"
    )


def main() -> None:
    # This script lives in processor/migration/, repo root is two levels above
    # (__file__ -> migration -> processor -> project root)
    root = Path(__file__).resolve().parents[2]
    segments_dir = root / "renderer" / "public" / "segments"
    transcripts_dir = root / "renderer" / "public" / "transcripts"
    sentences_dir = root / "renderer" / "public" / "sentences"

    if not segments_dir.exists():
        raise SystemExit(f"Segments directory not found: {segments_dir}")
    if not transcripts_dir.exists():
        raise SystemExit(f"Transcripts directory not found: {transcripts_dir}")
    if not sentences_dir.exists():
        raise SystemExit(f"Sentences directory not found: {sentences_dir}")

    output_dir = transcripts_dir  # store new files alongside existing ones

    # Determine which chapters have sentences files
    chapter_ids = sorted(
        [p.stem for p in sentences_dir.glob("c*.json") if p.stem.startswith("c")]
    )

    if not chapter_ids:
        print(f"No chapter sentences files found in {sentences_dir}")
        return

    print("Converting segment transcripts to sentence-based transcripts...")
    for chapter_id in chapter_ids:
        print(f"- Chapter {chapter_id}:")
        convert_chapter(
            chapter_id=chapter_id,
            sentences_dir=sentences_dir,
            segments_dir=segments_dir,
            transcripts_dir=transcripts_dir,
            output_dir=output_dir,
        )


if __name__ == "__main__":
    main()


