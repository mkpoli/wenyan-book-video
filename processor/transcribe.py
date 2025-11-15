import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import requests
    import regex as re
    from pathlib import Path
    import os

    return Path, os, re, requests


@app.cell(hide_code=True)
def _(Path, os, requests):
    import time
    from datetime import timedelta

    CACHE_MAX_AGE = timedelta(days=7)
    cache_root = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_dir = cache_root / "wenyan-book-video"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "qieyun_dictionary.txt"

    def cache_is_fresh(path: Path) -> bool:
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return False
        age = time.time() - mtime
        return age <= CACHE_MAX_AGE.total_seconds()

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
            if not isinstance(downloaded_text, str):
                raise RuntimeError(
                    "Unexpected non-text response when downloading Qieyun dictionary."
                )
            cache_path.write_text(downloaded_text, encoding="utf-8")
            dictionary_text = downloaded_text
            print(
                f"Dictionary downloaded and cached ({len(downloaded_text.splitlines())} lines)"
            )
        except Exception as download_error:
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
    return (dictionary_text,)


@app.cell(hide_code=True)
def _(dictionary_text):
    # Load dictionary: TSV format <char>\t<transcription>\t<frequency>
    dictionary = {}
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
        # Store as list of (transcription, frequency) tuples, sorted by frequency
        if ch not in dictionary:
            dictionary[ch] = []
        dictionary[ch].append((trans, freq))

    # Sort each character's readings by frequency (descending)
    for ch in dictionary:
        dictionary[ch].sort(key=lambda x: x[1], reverse=True)

    print(f"Dictionary loaded: {len(dictionary)} characters")
    return (dictionary,)


@app.cell(hide_code=True)
def _(Path):
    segments_dir = Path("../renderer/public/segments")
    transcripts_dir = Path("../renderer/public/transcripts")
    sentences_dir = Path("../renderer/public/sentences")

    # Ensure transcripts directory exists
    transcripts_dir.mkdir(exist_ok=True)
    sentences_dir.mkdir(exist_ok=True)
    return segments_dir, transcripts_dir, sentences_dir


@app.cell(hide_code=True)
def _(transcripts_dir, sentences_dir):
    import json as _json_init

    # Prepare sentence transcript files (c1.sentences.json, c2.sentences.json, ...)
    # for all chapters that have canonical sentences (c1.json, c2.json, ...).
    def sort_key(path):
        # Extract chapter number from filename like "c1.json" -> 1
        name = path.stem  # "c1"
        num_str = name.lstrip("c")
        return int(num_str) if num_str.isdigit() else 0

    sentence_files = []

    for sentences_path in sorted(sentences_dir.glob("c*.json"), key=sort_key):
        chapter_id = sentences_path.stem  # e.g. "c5"
        transcript_path = transcripts_dir / f"{chapter_id}.sentences.json"

        if not transcript_path.exists():
            # Initialize a sentence transcript file from canonical sentences.
            canon = _json_init.loads(sentences_path.read_text(encoding="utf-8"))
            _init_data: dict[str, dict[str, str]] = {}

            for s in canon.get("sentences", []):
                sid = s.get("id")
                _source = s.get("source", "")
                if not isinstance(sid, str) or not isinstance(_source, str):
                    continue
                _init_data[sid] = {"source": _source}

            transcript_path.write_text(
                _json_init.dumps(_init_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Created {transcript_path}")

        sentence_files.append(transcript_path)

    print(f"Prepared {len(sentence_files)} sentence transcript files")
    return (sentence_files,)


@app.cell
def _():
    # Character replacement rules for transcription
    CHAR_REPLACEMENTS = {
        "吿": "告",
        "为": "爲",
        "「": "",  # Remove CJK corner quotes
        "」": "",  # Remove CJK corner quotes
    }
    # No built-in SPECIAL_CASES here; see `special_cases.toml` for the
    # human-editable configuration of disambiguation choices.
    return CHAR_REPLACEMENTS


@app.cell(hide_code=True)
def _(CHAR_REPLACEMENTS, Path, os, re, requests):
    from functools import lru_cache
    import subprocess
    import json
    import tomllib
    from shutil import which
    from migration.cinix_to_tupa import convert_cinix_to_tupa

    def resolve_bun_executable() -> Path | None:
        """Locate Bun using environment hints or PATH."""
        bun_candidates: list[Path] = []

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

    lookup_script = Path(__file__).resolve().parent / "lookup_meaning.ts"
    lookup_cwd = lookup_script.parent
    bun_executable = resolve_bun_executable()
    lookup_script_exists = lookup_script.exists()
    bun_exists = bun_executable is not None

    def load_special_cases_config() -> dict[str, int]:
        """
        Load SPECIAL_CASES overrides from `special_cases.toml` on disk.

        The file is a human-editable TOML config with a `[special_cases]`
        table mapping characters to 0-based indices, e.g.:

          [special_cases]
          "不" = 0
          "冉" = 1

        This function is intentionally called each time we need to check
        special cases so that edits to the config file are picked up
        immediately during an interactive transcription session.
        """
        config_path = Path(__file__).resolve().parent / "special_cases.toml"

        merged: dict[str, int] = {}
        if not config_path.exists():
            return merged

        try:
            with config_path.open("rb") as f:
                cfg = tomllib.load(f)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Warning: Failed to load special cases config {config_path}: {exc}")
            return merged

        table = cfg.get("special_cases")
        if isinstance(table, dict):
            for key, value in table.items():
                if isinstance(key, str) and isinstance(value, int):
                    merged[key] = value

        return merged

    @lru_cache(maxsize=None)
    def _lookup_meaning_cached(
        char: str, readings_key: tuple[str, ...]
    ) -> list[dict[str, str]]:
        """
        Fetch transcription meanings using the local transcription helper.
        """

        if not char:
            return []
        if not lookup_script_exists:
            print(
                f"Warning: Local definition helper not found at {lookup_script}. "
                "Definitions will be omitted."
            )
            return []
        if not bun_exists or bun_executable is None:
            print(
                "Error: Bun executable not found in $BUN_INSTALL, $BUN_PATH, or PATH. "
                "Unable to load local definitions."
            )
            return []

        payload = {"entries": [{"char": char, "readings": list(readings_key)}]}

        try:
            completed = subprocess.run(
                [str(bun_executable), "run", str(lookup_script)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(lookup_cwd),
                check=True,
            )
        except FileNotFoundError:
            print(
                "Error: Bun executable became unavailable while invoking lookup helper."
            )
            return []
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            print(
                f"Warning: Local definition lookup failed for '{char}': "
                f"{stderr or exc}"
            )
            return []
        else:
            try:
                data = json.loads(completed.stdout or "{}")
            except json.JSONDecodeError as exc:
                print(
                    f"Warning: Invalid JSON from local definition lookup for '{char}': {exc}"
                )
                return []
            return data.get(char, [])

    @lru_cache(maxsize=None)
    def _lookup_meaning_remote(char: str) -> list[dict[str, str]]:
        """
        Fetch transcription meanings from the remote service as a fallback.
        """

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
        except Exception as exc:
            print(f"Warning: Remote definition lookup failed for '{char}': {exc}")
        return []

    def lookup_meaning(char: str, readings: list[str]) -> list[dict[str, str]]:
        """
        Return meanings for a single character keyed by its Cinix IPA readings.
        Falls back to the remote API only if local data lacks definitions.
        """

        readings_key = tuple(
            reading if isinstance(reading, str) else "" for reading in readings
        )
        local_results = _lookup_meaning_cached(char, readings_key) or []

        results_by_transcription: dict[str, dict[str, str | bool]] = {}
        for item in local_results:
            transcription = item.get("transcription")
            if not isinstance(transcription, str):
                continue
            meaning = item.get("meaning", "")
            has_definition = item.get("hasDefinition")
            if not isinstance(has_definition, bool):
                has_definition = (
                    bool(meaning.strip()) if isinstance(meaning, str) else False
                )
            results_by_transcription[transcription] = {
                "transcription": transcription,
                "meaning": meaning if isinstance(meaning, str) else "",
                "hasDefinition": has_definition,
            }

        missing_readings: list[str] = []
        for reading in readings_key:
            trimmed = reading if isinstance(reading, str) else ""
            if not trimmed:
                continue
            entry = results_by_transcription.get(trimmed)
            if entry is None or not entry.get("hasDefinition", False):
                missing_readings.append(trimmed)

        if missing_readings:
            remote_entries = _lookup_meaning_remote(char)
            remote_map: dict[str, str] = {}
            for item in remote_entries:
                transcription = item.get("transcription")
                meaning = item.get("meaning")
                if isinstance(transcription, str) and isinstance(meaning, str):
                    remote_map[transcription] = meaning

            for reading in missing_readings:
                remote_meaning = remote_map.get(reading)
                if not remote_meaning:
                    continue
                entry = results_by_transcription.get(reading)
                if entry:
                    base = entry.get("meaning", "")
                    base_str = base.strip() if isinstance(base, str) else ""
                    if base_str:
                        entry["meaning"] = f"{base_str} {remote_meaning}".strip()
                    else:
                        entry["meaning"] = remote_meaning
                    entry["hasDefinition"] = True
                else:
                    results_by_transcription[reading] = {
                        "transcription": reading,
                        "meaning": remote_meaning,
                        "hasDefinition": True,
                    }

        ordered_results: list[dict[str, str]] = []
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

    def replace_chars(text):
        """Replace characters according to replacement rules."""
        for old_char, new_char in CHAR_REPLACEMENTS.items():
            text = text.replace(old_char, new_char)
        return text

    def normalize_text(text):
        """Normalize text: remove whitespace, normalize punctuation.

        Inline code spans delimited by backticks (e.g. `code`) are removed
        entirely so they are ignored during transcription.
        """
        # Strip inline code spans first so they do not participate in
        # dictionary lookup or context display.
        text = re.sub(r"`[^`]*`", "", text)

        # Remove whitespace
        normalized = re.sub(r"\s+", "", text)
        # Normalize punctuation: map '。' → '.'
        normalized = normalized.replace("。", ".")
        # Ensure no duplicated trailing dots
        normalized = re.sub(r"\.+$", ".", normalized)
        return normalized

    def get_context(text: str, pos: int, min_chars: int = 10) -> tuple[str, str]:
        """
        Extract context around a character position.
        Shows at least min_chars before/after, extending to sentence boundaries (periods).

        Args:
            text: The normalized text
            pos: Position of the current character
            min_chars: Minimum characters to show before/after

        Returns:
            Tuple of (before_context, after_context)
        """
        # Find start position: go back at least min_chars, but extend to previous period
        start_pos = max(0, pos - min_chars)
        # Look for the previous period before start_pos
        for i in range(start_pos - 1, -1, -1):
            if text[i] == ".":
                start_pos = i + 1
                break
        else:
            # No period found, use beginning
            start_pos = 0

        # Find end position: go forward at least min_chars, but extend to next period
        end_pos = min(len(text), pos + 1 + min_chars)
        # Look for the next period after end_pos
        for i in range(end_pos, len(text)):
            if text[i] == ".":
                end_pos = i + 1
                break
        else:
            # No period found, use end
            end_pos = len(text)

        before_context = text[start_pos:pos]
        after_context = text[pos + 1 : end_pos]

        return before_context, after_context

    def transcribe_to_ipa(text, dictionary, choice_cache=None):
        """Transcribe Chinese text to IPA string.

        Args:
            text: Chinese text to transcribe
            dictionary: Dictionary mapping characters to list of (transcription, frequency) tuples
            choice_cache: Deprecated parameter (kept for compatibility, not used)
                          Characters in SPECIAL_CASES are automatically handled without prompting
        """

        normalized = normalize_text(text)

        # Convert each character to IPA
        ipa_parts = []
        # History of positions where user made choices (for characters with multiple readings)
        # Each entry is (position, character, ipa_parts_count_at_that_point)
        choice_history = []

        pos = 0
        while pos < len(normalized):
            ch = normalized[pos]
            if ch == ".":
                # Add period directly to IPA
                ipa_parts.append(".")
                pos += 1
            else:
                # Look up character in dictionary
                readings = dictionary.get(ch)
                if readings and len(readings) > 0:
                    # Check if we have multiple options
                    if len(readings) > 1:
                        # Check for special cases first (from editable config)
                        special_cases = load_special_cases_config()
                        if ch in special_cases:
                            # Special case: use specified choice index
                            choice_idx = special_cases[ch]
                            # Validate choice index is within bounds
                            if 0 <= choice_idx < len(readings):
                                # Show same information as non-special cases, but auto-select
                                print()

                                # Get and display context
                                before_context, after_context = get_context(
                                    normalized, pos
                                )
                                context_display = (
                                    f"{before_context}[{ch}]{after_context}"
                                )
                                print(f"Context: {context_display}")

                                # Fetch meanings to help with decision
                                reading_variants = [trans for trans, _ in readings]
                                char_meanings = lookup_meaning(ch, reading_variants)

                                # Create a mapping from transcription to meaning
                                trans_to_meaning = {}
                                for item in char_meanings:
                                    trans_to_meaning[item.get("transcription", "")] = (
                                        item.get("meaning", "")
                                    )

                                # Display all options with meanings
                                for idx, (trans, freq) in enumerate(readings, 1):
                                    meaning = trans_to_meaning.get(trans, "")
                                    display_value = meaning if meaning else trans
                                    selected_marker = (
                                        " ← SELECTED" if idx == choice_idx + 1 else ""
                                    )
                                    print(
                                        f" {f'<{idx}> ' if idx == choice_idx + 1 else f' {idx}. '} {display_value}{selected_marker}"
                                    )

                                transcription = readings[choice_idx][0]
                            else:
                                # Fallback to first choice if index is out of bounds
                                print(
                                    f"Warning: Special case choice index {choice_idx} for '{ch}' "
                                    f"is out of bounds (max: {len(readings)-1}), using 1st choice"
                                )
                                transcription = readings[0][0]

                            # Remove any periods from transcription (keep periods separate)
                            transcription = transcription.replace(".", "").strip()
                            if transcription:
                                ipa_parts.append(transcription)
                            pos += 1
                        else:
                            # Prompt user to choose
                            print()

                            # Get and display context
                            before_context, after_context = get_context(normalized, pos)
                            context_display = f"{before_context}[{ch}]{after_context}"
                            print(f"Context: {context_display}")

                            # Fetch meanings to help with decision
                            reading_variants = [trans for trans, _ in readings]
                            char_meanings = lookup_meaning(ch, reading_variants)

                            # Create a mapping from transcription to meaning
                            trans_to_meaning = {}
                            for item in char_meanings:
                                trans_to_meaning[item.get("transcription", "")] = (
                                    item.get("meaning", "")
                                )

                            for idx, (trans, freq) in enumerate(readings, 1):
                                meaning = trans_to_meaning.get(trans, "")
                                display_value = meaning if meaning else trans
                                print(f"  {idx}. {display_value}")

                            went_back = False
                            manual_transcription = None
                            while True:
                                try:
                                    back_option = (
                                        ", or 'b' to go back" if choice_history else ""
                                    )
                                    choice = input(
                                        f"Choose option (1-{len(readings)}, 'q' to save & quit, 'm' for manual input{back_option}): "
                                    ).strip()
                                    if choice.lower() == "q":
                                        # Save & quit the whole transcription run.
                                        # We signal this to the outer loop via KeyboardInterrupt.
                                        raise KeyboardInterrupt
                                    elif choice.lower() == "b":
                                        if choice_history:
                                            # Go back to last selection
                                            last_pos, last_ch, last_ipa_count = (
                                                choice_history.pop()
                                            )
                                            # Remove all transcriptions added after that point
                                            while len(ipa_parts) > last_ipa_count:
                                                ipa_parts.pop()
                                            # Set position back to that character
                                            pos = last_pos
                                            print(f"\n↶ Going back to: {last_ch}")
                                            went_back = True
                                            break
                                        else:
                                            print(
                                                "No previous selection to go back to."
                                            )
                                            continue
                                    elif choice.lower() == "m":
                                        manual_transcription = input(
                                            "Enter manual transcription: "
                                        ).strip()
                                        if manual_transcription:
                                            break
                                        else:
                                            print(
                                                "Manual transcription cannot be empty."
                                            )
                                            continue
                                    choice_idx = int(choice) - 1
                                    if 0 <= choice_idx < len(readings):
                                        break
                                    else:
                                        print(
                                            f"Please enter a number between 1 and {len(readings)}"
                                        )
                                except ValueError:
                                    print(
                                        "Please enter a valid number, 'q', 'm', or 'b'"
                                    )

                            # If we went back, continue the loop to re-process that character
                            if went_back:
                                continue

                            # Use manual transcription if provided, otherwise use dictionary choice
                            if manual_transcription is not None:
                                transcription = manual_transcription
                            else:
                                transcription = readings[choice_idx][0]

                            # Remove any periods from transcription (keep periods separate)
                            transcription = transcription.replace(".", "").strip()
                            if transcription:
                                # Record the count of ipa_parts before adding this transcription
                                ipa_count_before = len(ipa_parts)
                                ipa_parts.append(transcription)
                                # Add to history (only for user choices, not special cases)
                                # Store the count before adding, so we can remove everything after it when going back
                                choice_history.append((pos, ch, ipa_count_before))
                            pos += 1
                    else:
                        # Only one option, use it directly
                        transcription = readings[0][0]
                        # Remove any periods from transcription (keep periods separate)
                        transcription = transcription.replace(".", "").strip()
                        if transcription:
                            ipa_parts.append(transcription)
                        pos += 1
                else:
                    # Fallback: use character itself if not found
                    # Get and display context for warning
                    before_context, after_context = get_context(normalized, pos)
                    context_display = f"{before_context}[{ch}]{after_context}"
                    print(
                        f"\n⚠️  Warning: Character '{ch}' not found in dictionary (context: {context_display})"
                    )
                    ipa_parts.append(ch)
                    pos += 1

        # Join transcriptions with spaces.
        # Format: "word1 word2 . word3"
        # Filter out empty strings (periods are truthy so they'll be kept).
        ipa_parts = [p for p in ipa_parts if p]
        return " ".join(ipa_parts)

    return replace_chars, transcribe_to_ipa, convert_cinix_to_tupa


@app.cell(hide_code=True)
def _(
    dictionary,
    replace_chars,
    sentence_files,
    transcribe_to_ipa,
    transcripts_dir,
    convert_cinix_to_tupa,
):
    import json as _json

    # Shared choice cache across all sentences in all chapters
    choice_cache = {}

    # Process each chapter sentence-transcript file
    for sentence_file in sentence_files:
        print("\n" + "=" * 80)
        print(f"Transcribing sentence file: {sentence_file.name}")
        print("=" * 80)

        data = _json.loads(sentence_file.read_text(encoding="utf-8"))
        changed = False

        # Process sentences in numeric order (c1-s1, c1-s2, ...)
        def sent_sort_key(key: str) -> int:
            if "-s" in key:
                try:
                    return int(key.split("-s", 1)[1])
                except ValueError:
                    return 0
            return 0

        try:
            for sent_id in sorted(data.keys(), key=sent_sort_key):
                entry = data.get(sent_id) or {}
                source = entry.get("source")
                if not isinstance(source, str) or not source.strip():
                    continue

                # Skip sentences that already have a non-empty IPA string.
                # If we have already transcribed new sentences in this file
                # (`changed` is True), and we encounter an existing IPA in the
                # middle, stop processing this file to avoid crossing a
                # user-defined boundary.
                existing_ipa = entry.get("ipa")
                if isinstance(existing_ipa, str) and existing_ipa.strip():
                    if changed:
                        print(
                            f"  ↷ Encountered already-transcribed sentence {sent_id}; "
                            "stopping further transcription in this file."
                        )
                        break
                    continue

                # Apply character replacements
                text = replace_chars(source)

                # Transcribe to IPA (each character may prompt for disambiguation)
                ipa_text = transcribe_to_ipa(text, dictionary, choice_cache)
                entry["ipa"] = ipa_text

                # Also compute TUPA transcription from IPA
                entry["tupa"] = convert_cinix_to_tupa(ipa_text)

                data[sent_id] = entry
                changed = True
        except KeyboardInterrupt:
            # User requested save & quit ('q') during disambiguation.
            if changed:
                sentence_file.write_text(
                    _json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"\n✓ Saved partial updates for {sentence_file.name}")
            print("\n↯ Quit requested; stopping transcription.")
            raise SystemExit(0)

        if changed:
            sentence_file.write_text(
                _json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"✓ Saved updated sentence transcripts: {sentence_file.name}")
        else:
            print(f"✓ No changes needed for {sentence_file.name}")


if __name__ == "__main__":
    app.run()
