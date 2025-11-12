import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import requests
    import regex as re
    from pathlib import Path

    return Path, re, requests


@app.cell
def _(requests):
    # Download the dictionary
    print("Downloading dictionary...")
    dictionary_response = requests.get("https://qieyun-tts.com/dictionary_txt")
    if dictionary_response.status_code != 200:
        raise Exception(
            f"Failed to download dictionary: {dictionary_response.status_code}"
        )
    print(f"Dictionary downloaded: {len(dictionary_response.text.splitlines())} lines")
    dictionary_text = dictionary_response.text
    return (dictionary_text,)


@app.cell
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


@app.cell
def _(Path):
    segments_dir = Path("../renderer/public/segments")
    transcripts_dir = Path("../renderer/public/transcripts")

    # Ensure transcripts directory exists
    transcripts_dir.mkdir(exist_ok=True)
    return segments_dir, transcripts_dir


@app.cell
def _(re, requests):
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
    }

    def lookup_meaning(
        chars: str, base_url: str = "https://qieyun-tts.com"
    ) -> dict[str, list[dict]]:
        """
        Fetch transcription meanings from the /lookup_meaning endpoint.

        Args:
            chars: A string of unique Chinese characters to query.
            base_url: Root of the backend (no trailing slash).

        Returns:
            Dict like { '字': [ { 'transcription': '...', 'meaning': '...' }, ... ], ... }
        """
        try:
            response = requests.post(
                f"{base_url}/lookup_meaning", json={"chars": chars}, timeout=20.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Warning: Failed to lookup meanings: {e}")
            return {}

    def replace_chars(text):
        """Replace characters according to replacement rules."""
        for old_char, new_char in CHAR_REPLACEMENTS.items():
            text = text.replace(old_char, new_char)
        return text

    def normalize_text(text):
        """Normalize text: remove whitespace, normalize punctuation."""
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

    def transcribe_to_ipa(
        text, dictionary, choice_cache=None, base_url="https://qieyun-tts.com"
    ):
        """Transcribe Chinese text to IPA string.

        Args:
            text: Chinese text to transcribe
            dictionary: Dictionary mapping characters to list of (transcription, frequency) tuples
            choice_cache: Optional dict to cache user choices for characters with multiple readings
                          Characters in SPECIAL_CASES are automatically handled without prompting
            base_url: Base URL for the lookup_meaning API endpoint
        """
        if choice_cache is None:
            choice_cache = {}

        normalized = normalize_text(text)

        # Convert each character to IPA
        ipa_parts = []
        for pos, ch in enumerate(normalized):
            if ch == ".":
                # Add period directly to IPA
                ipa_parts.append(".")
            else:
                # Look up character in dictionary
                readings = dictionary.get(ch)
                if readings and len(readings) > 0:
                    # Check if we have multiple options
                    if len(readings) > 1:
                        # Check for special cases first
                        cache_key = ch
                        if ch in SPECIAL_CASES:
                            # Special case: use specified choice index
                            choice_idx = SPECIAL_CASES[ch]
                            # Validate choice index is within bounds
                            if 0 <= choice_idx < len(readings):
                                # Show same information as non-special cases, but auto-select
                                print(
                                    f"\nCharacter '{ch}' has {len(readings)} transcription options (SPECIAL_CASES - auto-selecting option {choice_idx + 1}):"
                                )

                                # Get and display context
                                before_context, after_context = get_context(
                                    normalized, pos
                                )
                                context_display = (
                                    f"{before_context}[{ch}]{after_context}"
                                )
                                print(f"Context: {context_display}")

                                # Fetch meanings to help with decision
                                meanings_data = lookup_meaning(ch, base_url)
                                char_meanings = meanings_data.get(ch, [])

                                # Create a mapping from transcription to meaning
                                trans_to_meaning = {}
                                for item in char_meanings:
                                    trans_to_meaning[item.get("transcription", "")] = (
                                        item.get("meaning", "")
                                    )

                                # Display all options with meanings
                                for idx, (trans, freq) in enumerate(readings, 1):
                                    meaning = trans_to_meaning.get(trans, "")
                                    meaning_str = f" - {meaning}" if meaning else ""
                                    selected_marker = (
                                        " ← SELECTED" if idx == choice_idx + 1 else ""
                                    )
                                    print(
                                        f"  {idx}. {trans} (frequency: {freq}){meaning_str}{selected_marker}"
                                    )

                                transcription = readings[choice_idx][0]
                                print(f"Automatically selected: {transcription}")
                            else:
                                # Fallback to first choice if index is out of bounds
                                print(
                                    f"Warning: Special case choice index {choice_idx} for '{ch}' "
                                    f"is out of bounds (max: {len(readings)-1}), using 1st choice"
                                )
                                transcription = readings[0][0]
                            # Cache the choice for consistency
                            choice_cache[cache_key] = transcription
                        elif cache_key in choice_cache:
                            # Use cached choice
                            transcription = choice_cache[cache_key]
                        else:
                            # Prompt user to choose
                            print(
                                f"\nCharacter '{ch}' has {len(readings)} transcription options:"
                            )

                            # Get and display context
                            before_context, after_context = get_context(normalized, pos)
                            context_display = f"{before_context}[{ch}]{after_context}"
                            print(f"Context: {context_display}")

                            # Fetch meanings to help with decision
                            meanings_data = lookup_meaning(ch, base_url)
                            char_meanings = meanings_data.get(ch, [])

                            # Create a mapping from transcription to meaning
                            trans_to_meaning = {}
                            for item in char_meanings:
                                trans_to_meaning[item.get("transcription", "")] = (
                                    item.get("meaning", "")
                                )

                            for idx, (trans, freq) in enumerate(readings, 1):
                                meaning = trans_to_meaning.get(trans, "")
                                meaning_str = f" - {meaning}" if meaning else ""
                                print(
                                    f"  {idx}. {trans} (frequency: {freq}){meaning_str}"
                                )

                            while True:
                                try:
                                    choice = input(
                                        f"Choose option (1-{len(readings)}, or 'q' to use default #1): "
                                    ).strip()
                                    if choice.lower() == "q":
                                        choice_idx = 0
                                        break
                                    choice_idx = int(choice) - 1
                                    if 0 <= choice_idx < len(readings):
                                        break
                                    else:
                                        print(
                                            f"Please enter a number between 1 and {len(readings)}"
                                        )
                                except ValueError:
                                    print("Please enter a valid number or 'q'")

                            transcription = readings[choice_idx][0]
                            # Cache the choice
                            choice_cache[cache_key] = transcription
                            print(f"Selected: {transcription}")
                    else:
                        # Only one option, use it directly
                        transcription = readings[0][0]

                    # Remove any periods from transcription (keep periods separate)
                    transcription = transcription.replace(".", "").strip()
                    if transcription:
                        ipa_parts.append(transcription)
                else:
                    # Fallback: use character itself if not found
                    ipa_parts.append(ch)

        # Join transcriptions with spaces
        # Format: " word1 word2 . word3 "
        # Filter out empty strings (periods are truthy so they'll be kept)
        ipa_parts = [p for p in ipa_parts if p]
        return " " + " ".join(ipa_parts) + " "

    return replace_chars, transcribe_to_ipa


@app.cell
def _(
    dictionary,
    replace_chars,
    segments_dir,
    transcribe_to_ipa,
    transcripts_dir,
):
    # Find all segment files
    # Sort naturally by extracting chapter and segment numbers
    def sort_key(path):
        # Extract numbers from filename like "1-2.txt" -> (1, 2)
        name = path.stem  # "1-2"
        parts = name.split("-")  # ["1", "2"]
        return (int(parts[0]), int(parts[1]))  # (chapter, segment)

    segment_files = sorted(segments_dir.glob("*.txt"), key=sort_key)

    print(f"Found {len(segment_files)} segment files")

    # Shared choice cache across all segments
    choice_cache = {}

    # Process each segment
    for segment_file in segment_files:
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

        print(f"Transcribing {segment_file.name}...")

        # Transcribe to IPA (pass choice_cache to remember user choices)
        ipa_text = transcribe_to_ipa(text, dictionary, choice_cache)

        # Save transcript
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(ipa_text)

        print(f"✓ Saved transcript: {transcript_filename}")
        print(f"  IPA: {ipa_text[:100]}...")
    return


if __name__ == "__main__":
    app.run()
