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

    # Ensure transcripts directory exists
    transcripts_dir.mkdir(exist_ok=True)
    return segments_dir, transcripts_dir


@app.cell(hide_code=True)
def _(segments_dir):
    # Find all segment files
    # Sort naturally by extracting chapter and segment numbers
    def sort_key(path):
        # Extract numbers from filename like "1-2.txt" -> (1, 2)
        name = path.stem  # "1-2"
        parts = name.split("-")  # ["1", "2"]
        return (int(parts[0]), int(parts[1]))  # (chapter, segment)

    segment_files = sorted(segments_dir.glob("*.txt"), key=sort_key)

    print(f"Found {len(segment_files)} segment files")
    return (segment_files,)


@app.cell
def _():
    # Character replacement rules for transcription
    CHAR_REPLACEMENTS = {
        "吿": "告",
        "为": "爲",
        "「": "",  # Remove CJK corner quotes
        "」": "",  # Remove CJK corner quotes
    }

    # Special cases: characters with preselected pronunciation choices
    # Maps character to choice index (0-based, where 0 = 1st choice)
    SPECIAL_CASES = {
        "不": 0,  # Always use 1st choice (index 0)
        "有": 0,  # Always use 1st choice (index 0),
        "編": 0,
        "造": 0,  # 【從|豪|上】造作又七到切 vs.【清|豪|去】至也又昨早切,
        "何": 0,  # 【匣|開|哥一|平】辝也說文儋也又姓出自周成王母弟唐叔虞後封於韓韓滅子孫分散江淮閒音以韓爲何字隨音變遂爲何氏出廬江東海陳郡三望胡歌切七 vs 【匣|開|哥一|上】上同（荷：負荷也胡可切又戶哥切二）,
        "事": 0,  # 【崇|之|去】使也立也由也鉏吏切又側吏切二 vs 【莊|之|去】事刃又作剚倳,
        "算": 0,  # 【心|合|寒|去】#同筭（筭：計也數也說文曰筭長六寸計歷數者也又有九章術漢許商杜忠吳陳熾魏王粲並善之世本曰黃帝時隷首作數蘇貫切四） vs 【心|合|寒|上】物之數也蘇管切三
        "視": 0,  # 【常|開|脂|上】比也瞻也效也承矢切三 vs 【常|開|脂|去】看視又音是,
        "其": 0,  # 【羣|之|平】辝也亦姓陽阿侯其石是也又漢複姓六氏左傳邾庶其之後以庶其爲氏世本楚大夫涉其帑漢清河都尉祝其承先王僧孺百家譜蘭陵蕭休緒娶高密侍其義叔女何氏姓苑有行其氏今其氏渠之切又音基三十 vs 【見|之|平】不其邑名在琅邪又人名漢有酈食其,
        "錯": 0,  # 【清|開|鐸|入】鑢別名又雜也摩也詩傳云東西爲交邪行爲錯說文云金涂也倉各切七 vs 【清|模|去】金塗又姓宋太宰之後又千各切
        "能": 0,  # 【泥|開|登|平】工善也又獸名熊屬足似鹿亦賢能也奴登切又奴代奴來二切一,
        "達": 0,  # 【定|開|末|入】通達亦姓出何氏姓苑又虜複姓三氏後魏獻帝弟爲達奚氏又達勃氏後改爲襃氏周文帝達步妃生齊煬王憲唐割切二 vs 【透|開|末|入】挑達往來皃又唐割切
        "西": 0,  # 【心|開|齊|平】秋方說文曰鳥在巢上也日在西方而鳥西故因以爲東西之西篆文作㢴象形亦州名本漢車師國之地至貞觀討平以其地爲西州亦姓又漢複姓十一氏左傳秦帥西乞術宋大夫西鉏吾西鄉錯出世本又黃帝娶西陵氏爲妃名纍祖史記魏文侯鄴令西門豹周末分爲東西二周武公庶子西周爲氏晉有北海西郭陽何承天以爲西朝名士慕容廆以北平西方虔爲股肱何氏姓苑有西野氏西宮氏王符潛夫論姓氏志曰如有東門西郭南宮北郭皆是因居也先稽切十六 vs 【心|開|先|平】#《集韻》金方也
        "列": 0,
        "如": 0,
        "左": 0,
        "吾": 0,
        "後": 0,
        "引": 0,
        "眾": 0,
        "方": 0,
        "猶": 0,
        "唯": 0,
        "逮": 0,
        "遠": 0,
        "使": 0,
        "演": 0,
        "識": 0,
        "與": 0,
        "取": 0,
        "道": 0,
        "精": 0,
        "要": 0,
        "定": 0,
        "足": 0,
        "觀": 0,
        "經": 0,
        "語": 0,
        "巧": 0,
        "蓋": 0,
        "半": 0,
        "迂": 0,
        "研": 0,
        "生": 0,
        "思": 0,
        "辨": 0,
        "走": 0,
        "氏": 0,
        "知": 0,
        "先": 0,
        "三": 0,
        "若": 0,
        "葉": 0,
        "數": 0,
        "減": 0,
        "留": 0,
        "句": 0,
        "創": 0,
        "祭": 0,
        "向": 0,
        "決": 0,
        "示": 0,
        "丁": 0,
        "伯": 0,
        "冉": 1,
        "風": 0,
        "科": 0,
        "弟": 0,
        "亡": 0,
        "複": 1,
        "嵌": 0,
        "樹": 0,
        "夫": 1,
        "父": 0,
        "土": 0,
    }
    return CHAR_REPLACEMENTS, SPECIAL_CASES


@app.cell(hide_code=True)
def _(CHAR_REPLACEMENTS, Path, SPECIAL_CASES, os, re, requests):
    from functools import lru_cache
    import subprocess
    import json
    from shutil import which

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
                        # Check for special cases first
                        if ch in SPECIAL_CASES:
                            # Special case: use specified choice index
                            choice_idx = SPECIAL_CASES[ch]
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
                                        f"Choose option (1-{len(readings)}, 'q' to use default #1, 'm' for manual input{back_option}): "
                                    ).strip()
                                    if choice.lower() == "q":
                                        choice_idx = 0
                                        break
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

        # Join transcriptions with spaces
        # Format: " word1 word2 . word3 "
        # Filter out empty strings (periods are truthy so they'll be kept)
        ipa_parts = [p for p in ipa_parts if p]
        return " " + " ".join(ipa_parts) + " "

    return replace_chars, transcribe_to_ipa


@app.cell(hide_code=True)
def _(
    dictionary,
    replace_chars,
    segment_files,
    transcribe_to_ipa,
    transcripts_dir,
):

    # Shared choice cache across all segments
    choice_cache = {}

    # Process each segment
    for segment_file in segment_files:
        print("\n" + "=" * 80)
        print(f"Transcribing: {segment_file.name}")
        print("=" * 80)

        # Check if transcript already exists
        transcript_filename = f"audio-{segment_file.stem}.txt"
        transcript_path = transcripts_dir / transcript_filename

        if transcript_path.exists():
            print(f"✓ Transcript already exists (skipped): {transcript_filename}")
            continue

        # Read segment text
        with open(segment_file, "r", encoding="utf-8") as f:
            text = f.read().strip()

        # Apply character replacements
        text = replace_chars(text)

        def wrap_text(text, length=40):
            return "\n".join(text[i : i + length] for i in range(0, len(text), length))

        print(f"{wrap_text(text)}")

        # Transcribe to IPA (each character will be prompted individually)
        ipa_text = transcribe_to_ipa(text, dictionary, choice_cache)

        # Save transcript
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(ipa_text)

        print(f"✓ Saved transcript: {transcript_filename}")
        print(f"  IPA: {ipa_text[:100]}...")
    return


if __name__ == "__main__":
    app.run()
