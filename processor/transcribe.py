from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from shutil import which
from typing import Any

import requests
import tomllib

from migration.cinix_to_tupa import convert_cinix_to_tupa


CURRENT_SENTENCE_CONTEXT: tuple[str | None, str | None] | None = None
LOOKUP_SCRIPT = Path(__file__).resolve().parent / "lookup_meaning.ts"


def download_dictionary_text() -> str:
    cache_root = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_dir = cache_root / "wenyan-book-video"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "qieyun_dictionary.txt"
    max_age = timedelta(days=7).total_seconds()

    def cache_is_fresh(path: Path) -> bool:
        try:
            return time.time() - path.stat().st_mtime <= max_age
        except FileNotFoundError:
            return False

    dictionary_text: str | None = None
    if cache_path.exists():
        if cache_is_fresh(cache_path):
            print(f"Using cached dictionary from {cache_path}")
            dictionary_text = cache_path.read_text(encoding="utf-8")
        else:
            print(
                f"Dictionary cache found but stale ({cache_path}), attempting refresh..."
            )
    else:
        print(f"No cached dictionary found at {cache_path}, downloading...")

    if dictionary_text is None:
        try:
            response = requests.get("https://qieyun-tts.com/dictionary_txt", timeout=30)
            response.raise_for_status()
            downloaded_text = response.text
            cache_path.write_text(downloaded_text, encoding="utf-8")
            dictionary_text = downloaded_text
            print(
                f"Dictionary downloaded and cached ({len(downloaded_text.splitlines())} lines)"
            )
        except Exception as download_error:  # noqa: BLE001
            if cache_path.exists():
                print(
                    "Warning: Failed to refresh dictionary, falling back to cached copy:"
                    f" {download_error}"
                )
                dictionary_text = cache_path.read_text(encoding="utf-8")
            else:
                raise RuntimeError(
                    "Failed to download Qieyun dictionary and no cache is available."
                ) from download_error

    return dictionary_text


def build_dictionary(dictionary_text: str) -> dict[str, list[tuple[str, int]]]:
    dictionary: dict[str, list[tuple[str, int]]] = {}
    for line in dictionary_text.splitlines():
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
        dictionary.setdefault(ch, []).append((trans, freq))

    for ch in dictionary:
        dictionary[ch].sort(key=lambda x: x[1], reverse=True)

    print(f"Dictionary loaded: {len(dictionary)} characters")
    return dictionary


def prepare_sentence_files(sentences_dir: Path, transcripts_dir: Path) -> list[Path]:
    def sort_key(path: Path) -> int:
        name = path.stem.split(".")[0]
        num_str = name.lstrip("c")
        return int(num_str) if num_str.isdigit() else 0

    sentence_files: list[Path] = []
    for sentences_path in sorted(sentences_dir.glob("c*.sentences.json"), key=sort_key):
        chapter_id = sentences_path.stem.split(".")[0]
        transcript_path = transcripts_dir / f"{chapter_id}.transcripts.json"

        if not transcript_path.exists():
            canon = json.loads(sentences_path.read_text(encoding="utf-8"))
            init_data: dict[str, dict[str, str]] = {}
            for s in canon.get("sentences", []):
                sid = s.get("id")
                source = s.get("source", "")
                if isinstance(sid, str) and isinstance(source, str):
                    init_data[sid] = {"source": source}

            transcript_path.write_text(
                json.dumps(init_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Created {transcript_path}")

        sentence_files.append(transcript_path)

    print(f"Prepared {len(sentence_files)} sentence transcript files")
    return sentence_files


def resolve_bun_executable() -> Path | None:
    candidates: list[Path] = []
    bun_install = os.getenv("BUN_INSTALL")
    if bun_install:
        candidates.append(Path(bun_install) / "bin" / "bun")
    bun_path = os.getenv("BUN_PATH")
    if bun_path:
        candidates.append(Path(bun_path))
    candidates.append(Path.home() / ".bun" / "bin" / "bun")
    found = which("bun")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


BUN_EXECUTABLE = resolve_bun_executable()
LOOKUP_SCRIPT_EXISTS = LOOKUP_SCRIPT.exists()


def load_special_cases_config() -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    config_path = Path(__file__).resolve().parent / "special_cases.toml"
    merged_char: dict[str, int] = {}
    merged_phrase: dict[str, dict[str, int]] = {}
    if not config_path.exists():
        return merged_char, merged_phrase
    try:
        with config_path.open("rb") as f:
            cfg = tomllib.load(f)
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: Failed to load special cases config {config_path}: {exc}")
        return merged_char, merged_phrase

    table = cfg.get("special_cases")
    if isinstance(table, dict):
        for key, value in table.items():
            if isinstance(key, str) and isinstance(value, int):
                merged_char[key] = value

    phrase_table = cfg.get("phrase_cases")
    if isinstance(phrase_table, dict):
        for phrase, overrides in phrase_table.items():
            if isinstance(phrase, str) and isinstance(overrides, dict):
                valid_overrides: dict[str, int] = {}
                for char_key, idx in overrides.items():
                    if isinstance(char_key, str) and isinstance(idx, int):
                        valid_overrides[char_key] = idx
                if valid_overrides:
                    merged_phrase[phrase] = valid_overrides

    return merged_char, merged_phrase


@lru_cache(maxsize=None)
def _lookup_meaning_cached(
    char: str, readings_key: tuple[str, ...]
) -> list[dict[str, str]]:
    if not char:
        return []
    if not LOOKUP_SCRIPT_EXISTS:
        print(
            f"Warning: Local definition helper not found at {LOOKUP_SCRIPT}. "
            "Definitions will be omitted."
        )
        return []
    if BUN_EXECUTABLE is None:
        print(
            "Error: Bun executable not found in $BUN_INSTALL, $BUN_PATH, or PATH. "
            "Unable to load local definitions."
        )
        return []

    readings_list: list[dict[str, str] | str] = []
    for r in readings_key:
        if isinstance(r, str):
            tupa = convert_cinix_to_tupa(r)
            readings_list.append({"original": r, "tupa": tupa})
        else:
            readings_list.append(str(r))

    payload = {"entries": [{"char": char, "readings": readings_list}]}

    try:
        completed = subprocess.run(
            [str(BUN_EXECUTABLE), "run", str(LOOKUP_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(LOOKUP_SCRIPT.parent),
            check=True,
        )
    except FileNotFoundError:
        print("Error: Bun executable became unavailable while invoking lookup helper.")
        return []
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        print(
            f"Warning: Local definition lookup failed for '{char}': " f"{stderr or exc}"
        )
        return []
    else:
        try:
            data = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            print(f"Warning: Invalid JSON from local definition lookup for '{char}': {exc}")
            return []
        results = data.get(char)
        return results if isinstance(results, list) else []


@lru_cache(maxsize=None)
def _lookup_meaning_remote(char: str) -> list[dict[str, str]]:
    if not char:
        return []
    try:
        response = requests.post(
            "https://qieyun-tts.com/lookup_meaning",
            json={"chars": char},
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            char_results = data.get(char)
            if isinstance(char_results, list):
                return char_results
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: Remote definition lookup failed for '{char}': {exc}")
    return []


def lookup_meaning(char: str, readings: list[str]) -> list[dict[str, str]]:
    readings_key = tuple(readings)
    local_results = _lookup_meaning_cached(char, readings_key) or []

    results_by_transcription: dict[str, dict[str, Any]] = {}
    for item in local_results:
        transcription = item.get("transcription")
        if not isinstance(transcription, str):
            continue
        meaning = item.get("meaning", "")
        results_by_transcription[transcription] = {
            "transcription": transcription,
            "meaning": meaning if isinstance(meaning, str) else "",
            "hasDefinition": bool(meaning.strip()),
        }

    missing_readings: list[str] = []
    for reading in readings_key:
        trimmed = reading if isinstance(reading, str) else ""
        if not trimmed:
            continue
        entry = results_by_transcription.get(trimmed)
        if entry is None or not entry.get("hasDefinition"):
            missing_readings.append(trimmed)

    if missing_readings:
        for remote_entry in _lookup_meaning_remote(char):
            transcription = remote_entry.get("transcription")
            meaning = remote_entry.get("meaning")
            if isinstance(transcription, str) and isinstance(meaning, str):
                entry = results_by_transcription.setdefault(
                    transcription,
                    {"transcription": transcription, "meaning": "", "hasDefinition": False},
                )
                if not entry["meaning"]:
                    entry["meaning"] = meaning
                entry["hasDefinition"] = True

    ordered_results: list[dict[str, str]] = []
    for reading in readings_key:
        trimmed = reading if isinstance(reading, str) else ""
        if not trimmed:
            continue
        entry = results_by_transcription.get(trimmed)
        if entry:
            ordered_results.append(
                {
                    "transcription": trimmed,
                    "meaning": entry.get("meaning", ""),
                }
            )
        else:
            ordered_results.append({"transcription": trimmed, "meaning": ""})

    return ordered_results


CHAR_REPLACEMENTS = {
    "吿": "告",
    "为": "爲",
    "「": "",
    "」": "",
}


def replace_chars(text: str) -> str:
    for old_char, new_char in CHAR_REPLACEMENTS.items():
        text = text.replace(old_char, new_char)
    return text


def normalize_text(text: str) -> str:
    # Inline code markers should not remove the enclosed content; strip only the
    # backtick characters so transcription still "sees" the underlying text.
    text = text.replace("`", "")
    normalized = re.sub(r"\s+", "", text)
    normalized = normalized.replace("。", ".")
    normalized = re.sub(r"\.+$", ".", normalized)
    return normalized


def set_sentence_context(prev_source: str | None, next_source: str | None) -> None:
    global CURRENT_SENTENCE_CONTEXT
    CURRENT_SENTENCE_CONTEXT = (prev_source, next_source)


def get_context(text: str, pos: int, min_chars: int = 10) -> tuple[str, str]:
    before_core = text[:pos].rstrip(".")
    after_core = text[pos + 1 :].lstrip(".")

    prev_source: str | None = None
    next_source: str | None = None
    if CURRENT_SENTENCE_CONTEXT is not None:
        prev_source, next_source = CURRENT_SENTENCE_CONTEXT

    before_core = before_core.replace(".", "。")
    after_core = after_core.replace(".", "。")

    before_context = ""
    prev_trimmed = prev_source.rstrip("。").strip() if prev_source else ""
    if prev_trimmed:
        before_context += prev_trimmed
    if before_core:
        if prev_trimmed:
            before_context += "。"
        before_context += before_core

    after_context = ""
    if after_core:
        after_context += after_core
    if next_source:
        after_context += next_source

    if not before_context and not after_context:
        before_context = text[max(0, pos - min_chars) : pos]
        after_context = text[pos + 1 : pos + 1 + min_chars]

    return before_context, after_context


def transcribe_to_ipa(text: str, dictionary: dict[str, list[tuple[str, int]]]) -> str:
    normalized = normalize_text(text)
    ipa_parts: list[str] = []
    choice_history: list[tuple[int, str, int]] = []

    pos = 0
    while pos < len(normalized):
        ch = normalized[pos]
        if ch == ".":
            ipa_parts.append(".")
            pos += 1
            continue

        readings = dictionary.get(ch)
        if readings and len(readings) > 0:

            if len(readings) > 1:
                special_cases, phrase_cases = load_special_cases_config()
                choice_idx = -1

                # 1. Check phrase-level overrides
                for phrase, overrides in phrase_cases.items():
                    if ch in overrides:
                        # Check if 'phrase' matches normalized text around 'pos'
                        for k, p_char in enumerate(phrase):
                            if p_char == ch:
                                start = pos - k
                                end = start + len(phrase)
                                if start >= 0 and end <= len(normalized):
                                    candidate = normalized[start:end]
                                    if candidate == phrase:
                                        choice_idx = overrides[ch]
                                        break
                        if choice_idx != -1:
                            break

                # 2. Check character-level overrides
                if choice_idx == -1 and ch in special_cases:
                    choice_idx = special_cases[ch]

                if choice_idx != -1:
                    if 0 <= choice_idx < len(readings):
                        print()
                        before_context, after_context = get_context(normalized, pos)
                        context_display = f"{before_context}[{ch}]{after_context}"
                        print(f"Context: {context_display}")
                        reading_variants = [trans for trans, _ in readings]
                        char_meanings = lookup_meaning(ch, reading_variants)
                        trans_to_meaning = {
                            item.get("transcription", ""): item.get("meaning", "")
                            for item in char_meanings
                        }
                        for idx, (trans, _) in enumerate(readings, 1):
                            meaning = trans_to_meaning.get(trans, "")
                            display_value = meaning if meaning else trans
                            selected = " ← SELECTED" if idx == choice_idx + 1 else ""
                            label = "<" if idx == choice_idx + 1 else ""
                            print(f" {label}{idx}> {display_value}{selected}")
                        transcription = readings[choice_idx][0]
                    else:
                        print(
                            f"Warning: Special case choice index {choice_idx} for '{ch}' is out of bounds; using first choice."
                        )
                        transcription = readings[0][0]
                    transcription = transcription.replace(".", "").strip()
                    if transcription:
                        ipa_parts.append(transcription)
                    pos += 1
                    continue

                print()
                before_context, after_context = get_context(normalized, pos)
                context_display = f"{before_context}[{ch}]{after_context}"
                print(f"Context: {context_display}")
                reading_variants = [trans for trans, _ in readings]
                char_meanings = lookup_meaning(ch, reading_variants)
                trans_to_meaning = {
                    item.get("transcription", ""): item.get("meaning", "")
                    for item in char_meanings
                }
                while True:
                    for idx, (trans, _) in enumerate(readings, 1):
                        meaning = trans_to_meaning.get(trans, "")
                        display_value = meaning if meaning else trans
                        print(f"  {idx}. {display_value}")

                    choice = input(
                        "Choose reading (number), 'q' to save & quit, 'b' to go back, 'm' for manual: "
                    ).strip()

                    if choice.lower() == "q":
                        raise KeyboardInterrupt
                    if choice.lower() == "b":
                        if choice_history:
                            last_pos, _, ipa_count_before = choice_history.pop()
                            ipa_parts = ipa_parts[:ipa_count_before]
                            pos = last_pos
                            break
                        print("No previous choices to undo.")
                        continue
                    if choice.lower() == "m":
                        manual = input("Enter manual transcription: ").strip()
                        if manual:
                            transcription = manual
                            break
                        print("Manual transcription cannot be empty.")
                        continue

                    try:
                        choice_idx = int(choice) - 1
                    except ValueError:
                        print("Please enter a valid number, 'q', 'm', or 'b'")
                        continue
                    if 0 <= choice_idx < len(readings):
                        transcription = readings[choice_idx][0]
                        break
                    print(f"Please enter a number between 1 and {len(readings)}")

                else:  # pragma: no cover - guard for loop structure
                    continue

                transcription = transcription.replace(".", "").strip()
                if transcription:
                    ipa_count_before = len(ipa_parts)
                    ipa_parts.append(transcription)
                    choice_history.append((pos, ch, ipa_count_before))
                pos += 1
            else:
                transcription = readings[0][0].replace(".", "").strip()
                if transcription:
                    ipa_parts.append(transcription)
                pos += 1
        else:
            before_context, after_context = get_context(normalized, pos)
            context_display = f"{before_context}[{ch}]{after_context}"
            print(
                f"\n⚠️  Warning: Character '{ch}' not found in dictionary (context: {context_display})"
            )
            ipa_parts.append(ch)
            pos += 1

    ipa_parts = [p for p in ipa_parts if p]
    return " ".join(ipa_parts)


def transcribe_sentence_files(
    sentence_files: list[Path],
    sentences_dir: Path,
    dictionary: dict[str, list[tuple[str, int]]],
) -> None:
    for sentence_file in sentence_files:
        print("\n" + "=" * 80)
        print(f"Transcribing sentence file: {sentence_file.name}")
        print("=" * 80)

        data = json.loads(sentence_file.read_text(encoding="utf-8"))
        changed = False
        chapter_id = sentence_file.stem.split(".")[0]
        canon_path = sentences_dir / f"{chapter_id}.sentences.json"
        canon_sentences = []
        if canon_path.exists():
            canon_data = json.loads(canon_path.read_text(encoding="utf-8"))
            canon_sentences = canon_data.get("sentences", [])
        sentence_index_by_id = {
            entry.get("id"): idx for idx, entry in enumerate(canon_sentences)
        }

        try:
            logged_skip_after_change = False
            for sent_id, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                source = entry.get("source", "")
                if not isinstance(source, str) or not source.strip():
                    continue

                existing_ipa = entry.get("ipa")
                if isinstance(existing_ipa, str) and existing_ipa.strip():
                    if changed and not logged_skip_after_change:
                        print(
                            "  ↷ Encountered already-transcribed sentence "
                            f"{sent_id}; continuing to the next unfinished sentence."
                        )
                        logged_skip_after_change = True
                    continue

                prev_source = None
                next_source = None
                idx = sentence_index_by_id.get(sent_id)
                if isinstance(idx, int) and canon_sentences:
                    if idx > 0:
                        prev = canon_sentences[idx - 1].get("source")
                        if isinstance(prev, str) and prev.strip():
                            prev_source = prev
                    if idx + 1 < len(canon_sentences):
                        nxt = canon_sentences[idx + 1].get("source")
                        if isinstance(nxt, str) and nxt.strip():
                            next_source = nxt

                set_sentence_context(prev_source, next_source)
                text = replace_chars(source)
                ipa_text = transcribe_to_ipa(text, dictionary)
                entry["ipa"] = ipa_text
                entry["tupa"] = convert_cinix_to_tupa(ipa_text)
                data[sent_id] = entry
                changed = True
        except KeyboardInterrupt:
            if changed:
                sentence_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"\n✓ Saved partial updates for {sentence_file.name}")
            print("\n↯ Quit requested; stopping transcription.")
            raise SystemExit(0)

        if changed:
            sentence_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"✓ Saved updated sentence transcripts: {sentence_file.name}")
        else:
            print(f"✓ No changes needed for {sentence_file.name}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    transcripts_dir = root / "renderer" / "public" / "transcripts"
    sentences_dir = root / "renderer" / "public" / "sentences"
    transcripts_dir.mkdir(exist_ok=True)
    sentences_dir.mkdir(exist_ok=True)

    dictionary_text = download_dictionary_text()
    dictionary = build_dictionary(dictionary_text)
    sentence_files = prepare_sentence_files(sentences_dir, transcripts_dir)
    if not sentence_files:
        print("No sentence transcript files found; nothing to do.")
        return
    transcribe_sentence_files(sentence_files, sentences_dir, dictionary)


if __name__ == "__main__":
    main()
