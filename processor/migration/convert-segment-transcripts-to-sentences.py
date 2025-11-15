from __future__ import annotations

import json
import os
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from shutil import which
from typing import Any, Dict, List, Tuple

from cinix_to_tupa import convert_cinix_to_tupa


def load_qieyun_dictionary() -> Dict[str, List[Tuple[str, int]]]:
    """
    Load the Qieyun dictionary from the same cache location used by transcribe.py.

    If the cache file is missing, returns an empty dict and callers should
    gracefully skip choice annotation.
    """
    cache_root = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_dir = cache_root / "wenyan-book-video"
    cache_path = cache_dir / "qieyun_dictionary.txt"

    if not cache_path.exists():
        print(
            f"  ⚠ Qieyun dictionary cache not found at {cache_path}; "
            "choices metadata will be omitted."
        )
        return {}

    dictionary: Dict[str, List[Tuple[str, int]]] = {}
    text = cache_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        ch, trans, freq_s = parts
        try:
            freq = int(freq_s)
        except ValueError:
            freq = 0
        if ch not in dictionary:
            dictionary[ch] = []
        dictionary[ch].append((trans, freq))

    for ch in dictionary:
        dictionary[ch].sort(key=lambda x: x[1], reverse=True)

    print(f"  ℹ Loaded Qieyun dictionary: {len(dictionary)} characters")
    return dictionary


def resolve_bun_executable() -> Path | None:
    """Locate Bun using environment hints or PATH."""
    bun_candidates: List[Path] = []

    bun_install = os.getenv("BUN_INSTALL")
    if bun_install:
        bun_candidates.append(Path(bun_install) / "bin" / "bun")

    bun_path = os.getenv("BUN_PATH")
    if bun_path:
        bun_candidates.append(Path(bun_path))

    default_install = Path.home() / ".bun" / "bin" / "bun"
    bun_candidates.append(default_install)

    path_candidate = which("bun")
    if path_candidate:
        bun_candidates.append(Path(path_candidate))

    for candidate in bun_candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    return None


LOOKUP_SCRIPT = Path(__file__).resolve().parents[1] / "lookup_meaning.ts"
LOOKUP_CWD = LOOKUP_SCRIPT.parent
BUN_EXECUTABLE = resolve_bun_executable()
LOOKUP_SCRIPT_EXISTS = LOOKUP_SCRIPT.exists()
BUN_EXISTS = BUN_EXECUTABLE is not None


@lru_cache(maxsize=None)
def _lookup_meaning_cached(
    char: str, readings_key: Tuple[str, ...]
) -> List[Dict[str, str]]:
    """
    Fetch transcription meanings using the local transcription helper.

    This mirrors the behavior in transcribe.py but omits the remote fallback:
    for migration we only rely on local data.
    """

    if not char:
        return []
    if not LOOKUP_SCRIPT_EXISTS:
        print(
            f"  ⚠ Local definition helper not found at {LOOKUP_SCRIPT}. "
            "Choices will omit meanings."
        )
        return []
    if not BUN_EXISTS or BUN_EXECUTABLE is None:
        print(
            "  ⚠ Bun executable not found in $BUN_INSTALL, $BUN_PATH, or PATH. "
            "Choices will omit meanings."
        )
        return []

    payload = {"entries": [{"char": char, "readings": list(readings_key)}]}

    try:
        completed = subprocess.run(
            [str(BUN_EXECUTABLE), "run", str(LOOKUP_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(LOOKUP_CWD),
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        stderr = ""
        if isinstance(exc, subprocess.CalledProcessError):
            stderr = (exc.stderr or "").strip()
        print(f"  ⚠ Local definition lookup failed for '{char}': " f"{stderr or exc}")
        return []
    else:
        try:
            data = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            print(f"  ⚠ Invalid JSON from local definition lookup for '{char}': {exc}")
            return []
        results = data.get(char)
        return results if isinstance(results, list) else []


def lookup_meaning(char: str, readings: List[str]) -> List[Dict[str, str]]:
    """
    Return meanings for a single character keyed by its Cinix IPA readings.

    The result is a list of objects like:
      { "transcription": "...", "meaning": "..." }
    in the same order as the provided readings.
    """

    readings_key = tuple(readings)
    local_results = _lookup_meaning_cached(char, readings_key) or []

    results_by_transcription: Dict[str, Dict[str, Any]] = {}
    for item in local_results:
        transcription = item.get("transcription")
        if not isinstance(transcription, str):
            continue
        meaning = item.get("meaning", "")
        results_by_transcription[transcription] = {
            "transcription": transcription,
            "meaning": meaning if isinstance(meaning, str) else "",
        }

    ordered_results: List[Dict[str, str]] = []
    for reading in readings_key:
        trimmed = reading if isinstance(reading, str) else ""
        if not trimmed:
            continue
        entry = results_by_transcription.get(trimmed)
        if entry:
            meaning_value = entry.get("meaning")
            ordered_results.append(
                {
                    "transcription": trimmed,
                    "meaning": (
                        meaning_value if isinstance(meaning_value, str) else ""
                    ),
                }
            )
        else:
            ordered_results.append({"transcription": trimmed, "meaning": ""})

    return ordered_results


# Character replacement rules used during transcription; we reuse them to
# align dictionary lookups with canonical sentence sources.
CHAR_REPLACEMENTS: Dict[str, str] = {
    "吿": "告",
    "为": "爲",
    "「": "",
    "」": "",
}


def is_chinese_char(ch: str) -> bool:
    """Rudimentary check for CJK ideographs."""
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0x2B740 <= code <= 0x2B81F
        or 0x2B820 <= code <= 0x2CEAF
        or 0xF900 <= code <= 0xFAFF
    )


def build_choices_for_sentence(
    source: str,
    ipa: str,
    dictionary: Dict[str, List[Tuple[str, int]]],
) -> List[Dict[str, Any]]:
    """
    Infer pronunciation choices for characters with multiple readings.

    For each such character, we record:
      - char: the original character in the sentence
      - indexInSource: index in the sentence's source string
      - indexAmongChinese: index among Chinese characters only
      - sameCharIndex: occurrence index among the same character in this sentence
      - ipa: the Cinix IPA token actually used in the transcript (without '.')
      - tupa: TUPA representation derived from ipa
    """
    if not source or not ipa or not dictionary:
        return []

    # Enumerate Chinese characters with positional metadata.
    chinese_positions: List[Dict[str, Any]] = []
    same_char_counter: Dict[str, int] = defaultdict(int)
    chinese_index = 0

    for index_in_source, ch in enumerate(source):
        if not is_chinese_char(ch):
            continue

        char_for_dict = CHAR_REPLACEMENTS.get(ch, ch)
        occurrence_index = same_char_counter[ch]
        same_char_counter[ch] += 1

        chinese_positions.append(
            {
                "char": ch,
                "char_for_dict": char_for_dict,
                "indexInSource": index_in_source,
                "indexAmongChinese": chinese_index,
                "sameCharIndex": occurrence_index,
            }
        )
        chinese_index += 1

    if not chinese_positions:
        return []

    # Tokenize the IPA string; tokens include '.' as separate items.
    ipa_tokens = [tok for tok in ipa.strip().split() if tok]
    if not ipa_tokens:
        return []

    # Align each Chinese character with the next non-period IPA token.
    token_idx = 0
    for pos in chinese_positions:
        while token_idx < len(ipa_tokens) and ipa_tokens[token_idx] == ".":
            token_idx += 1
        if token_idx >= len(ipa_tokens):
            break
        pos["ipa"] = ipa_tokens[token_idx]
        token_idx += 1

    choices: List[Dict[str, Any]] = []

    for pos in chinese_positions:
        ipa_token = pos.get("ipa")
        ch_dict = pos["char_for_dict"]
        if not ipa_token or not ch_dict:
            continue

        readings = dictionary.get(ch_dict) or []
        if len(readings) <= 1:
            # Only care about characters with multiple dictionary readings.
            continue

        # Since chosen_cinix is always equal to ipa_token, use ipa_token directly for tupa conversion
        chosen_tupa = convert_cinix_to_tupa(ipa_token) if ipa_token else ""

        choices.append(
            {
                "char": pos["char"],
                "indexInSource": pos["indexInSource"],
                "indexAmongChinese": pos["indexAmongChinese"],
                "sameCharIndex": pos["sameCharIndex"],
                "ipa": ipa_token,
                "tupa": chosen_tupa,
            }
        )

    return choices


def split_chinese_sentences(text: str) -> List[str]:
    """
    Split Chinese text into sentences ending with '。'.
    Mirrors the logic used in segment-text and build-sentences.
    Handles quoted text properly (e.g., '。』。' should not split).
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

    # For migration we want to keep sentences that may end with closing
    # quotes (e.g. 「…。」』), so don't drop sentences that don't literally
    # end in 。/！/？. Just remove empty fragments.
    return [s for s in sentences if s]


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


def rebalance_ipa_sentences_for_segment(
    cn_sentences: List[str],
    ipa_sentences: List[str],
) -> List[str]:
    """
    When a segment's Chinese sentences and IPA sentences don't match in count,
    but the *total* number of written sentence endings matches, we can often
    recover alignment by merging adjacent IPA sentences.

    Heuristic:
      - For each Chinese sentence, count occurrences of '。'.
      - If the sum of these counts equals len(ipa_sentences), we treat each
        '。' as one prosodic unit and assign that many IPA sentences to the
        corresponding Chinese sentence, merging them when there are multiple.

    Example (segment 4-14.txt):
      CN[1]: 曰『爾雖人。於我實芻狗也。』  -> 2 x '。'
      IPA[1]: ... .   IPA[2]: ... .
      => merged IPA for CN[1]: IPA[1] + IPA[2]
    """

    if not cn_sentences or not ipa_sentences:
        return ipa_sentences

    # Count sentence-ending marks in each Chinese sentence
    endings_per_cn: List[int] = []
    for s in cn_sentences:
        count = s.count("。")
        # Fallback: if there is no '。' but the sentence is non-empty, treat as 1
        if count == 0 and s.strip():
            count = 1
        endings_per_cn.append(count)

    total_endings = sum(endings_per_cn)
    if total_endings != len(ipa_sentences):
        # Can't rebalance safely; keep original IPA sentences.
        return ipa_sentences

    rebalanced: List[str] = []
    ipa_index = 0

    for count in endings_per_cn:
        # Merge `count` IPA sentences for this Chinese sentence.
        merged = " ".join(ipa_sentences[ipa_index : ipa_index + count]).strip()
        rebalanced.append(merged)
        ipa_index += count

    return rebalanced


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
    dictionary: Dict[str, List[Tuple[str, int]]],
) -> None:
    """
    Convert existing segment-based transcripts for one chapter into
    sentence-based transcripts.
    """
    # Canonical sentences are stored as `c{n}.sentences.json`.
    sentences_path = sentences_dir / f"{chapter_id}.sentences.json"
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

    # Check if any transcript files exist for this chapter
    transcript_files = list(transcripts_dir.glob(f"audio-{chapter_num}-*.txt"))
    if not transcript_files:
        print(f"  ⚠ No transcript files found for chapter {chapter_num}, skipping.")
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
                # Try to rebalance by merging adjacent IPA sentences based on
                # how many '。' appear in each Chinese sentence.
                rebalanced = rebalance_ipa_sentences_for_segment(
                    cn_sentences, ipa_sentences
                )
                if len(rebalanced) == len(cn_sentences):
                    print(
                        f"  ℹ Rebalanced IPA sentences for {seg_path.name}: "
                        f"{len(ipa_sentences)} -> {len(rebalanced)}"
                    )
                    ipa_sentences = rebalanced
                else:
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

                        # Detailed debug dump to help inspect mismatches, but only
                        # for shorter segments to avoid flooding the logs.
                        if len(cn_sentences) <= 20 and len(ipa_sentences) <= 20:
                            print("    Chinese sentences:")
                            for idx, s in enumerate(cn_sentences):
                                print(f"      CN[{idx}]: {s}")
                            print("    IPA sentences:")
                            for idx, s in enumerate(ipa_sentences):
                                print(f"      IPA[{idx}]: {s}")

        # Map this segment's sentences onto chapter sentences
        ipa_index = 0  # index into ipa_sentences for this segment
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

            # Normalize for comparison: remove backticks and normalize whitespace
            def normalize_for_comparison(text: str) -> str:
                # Remove backticks (used in code sentences)
                text = text.replace("`", "")
                # Normalize whitespace
                import re

                text = re.sub(r"\s+", " ", text)
                return text.strip()

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
                # Check if there's a next canonical sentence that also fits in the segment sentence
                if sent_index + 1 < len(chapter_sentences):
                    next_canonical = chapter_sentences[sent_index + 1].get("source", "")
                    next_normalized = normalize_for_comparison(next_canonical)
                    if next_normalized:
                        # Check if segment sentence contains both canonical sentences
                        combined = canonical_normalized + " " + next_normalized
                        if combined.replace(" ", "") in cn_normalized.replace(" ", ""):
                            spans_multiple = True

            if (
                isinstance(canonical_source, str)
                and canonical_normalized != cn_normalized
                and not spans_multiple
            ):
                # Simple sanity check; still proceed.
                # Only warn if the normalized versions don't match and one doesn't contain the other
                if (
                    canonical_normalized not in cn_normalized
                    and cn_normalized not in canonical_normalized
                ):
                    print(
                        f"  ⚠ Sentence mismatch in {seg_path.name} at chapter index {sent_index}:"
                        f"\n     canonical: {canonical_source}"
                        f"\n     segment:   {cn_sentence}"
                    )

            if spans_multiple and ipa_sentences and ipa_index + 1 < len(ipa_sentences):
                # Segment sentence spans two canonical sentences - consume two IPA sentences
                # First canonical sentence
                ipa_1 = ipa_sentences[ipa_index]
                if sent_id and ipa_1:
                    entry: Dict[str, Any] = {
                        "source": canonical_source,
                        "ipa": ipa_1,
                        "tupa": convert_cinix_to_tupa(ipa_1),
                    }
                    choices = build_choices_for_sentence(
                        canonical_source,
                        ipa_1,
                        dictionary,
                    )
                    if choices:
                        entry["choices"] = choices
                    result[sent_id] = entry
                sent_index += 1

                # Second canonical sentence
                if sent_index < len(chapter_sentences):
                    next_entry = chapter_sentences[sent_index]
                    next_sent_id = next_entry.get("id")
                    ipa_2 = ipa_sentences[ipa_index + 1]
                    if next_sent_id and ipa_2:
                        entry2: Dict[str, Any] = {
                            "source": next_entry.get("source", ""),
                            "ipa": ipa_2,
                            "tupa": convert_cinix_to_tupa(ipa_2),
                        }
                        choices2 = build_choices_for_sentence(
                            next_entry.get("source", ""),
                            ipa_2,
                            dictionary,
                        )
                        if choices2:
                            entry2["choices"] = choices2
                        result[next_sent_id] = entry2
                    sent_index += 1

                # We consumed two IPA sentences
                ipa_index += 2

                # Skip the rest of the loop - we've already processed this segment sentence
                continue

            # Normal single-sentence mapping
            ipa_value = ""
            if ipa_sentences and ipa_index < len(ipa_sentences):
                ipa_value = ipa_sentences[ipa_index]

            if sent_id and ipa_value:
                entry: Dict[str, Any] = {
                    "source": canonical_source,
                    "ipa": ipa_value,
                    "tupa": convert_cinix_to_tupa(ipa_value),
                }
                choices = build_choices_for_sentence(
                    canonical_source,
                    ipa_value,
                    dictionary,
                )
                if choices:
                    entry["choices"] = choices
                result[sent_id] = entry

            # Advance to the next canonical and IPA sentence
            sent_index += 1
            if ipa_sentences and ipa_index < len(ipa_sentences):
                ipa_index += 1

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

    dictionary = load_qieyun_dictionary()

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
            dictionary=dictionary,
        )


if __name__ == "__main__":
    main()
