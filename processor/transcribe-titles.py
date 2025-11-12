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
    book_dir = Path("../book")
    transcripts_dir = Path("../renderer/public/transcripts")

    # Ensure transcripts directory exists
    transcripts_dir.mkdir(exist_ok=True)
    return book_dir, transcripts_dir


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
    SPECIAL_CASES = {
        # "不": 0,
        # "有": 0,
        # "編": 0,
        # "造": 0,
        # "何": 0,
        # "事": 0,
        # "算": 0,
        # "視": 0,
        # "其": 0,
        # "錯": 0,
        # "能": 0,
        # "達": 0,
        # "西": 0,
        # "明": 0,
        # "義": 0,
        # "第": 0,
        # "一": 0,
        # "變": 0,
        # "數": 0,
        # "二": 0,
        # "術": 0,
        # "三": 0,
        # "決": 0,
        # "策": 0,
        # "四": 0,
        # "循": 0,
        # "環": 0,
        # "五": 0,
        # "行": 0,
        # "列": 0,
        # "六": 0,
        # "言": 0,
        # "語": 0,
        # "七": 0,
        # "方": 0,
        # "八": 0,
        # "府": 0,
        # "庫": 0,
        # "九": 0,
        # "格": 0,
        # "物": 0,
        # "十": 0,
        # "克": 0,
        # "禍": 0,
        # "圖": 0,
        # "畫": 0,
        # "宏": 0,
        # "略": 0,
    }

    def lookup_meaning(
        chars: str, base_url: str = "https://qieyun-tts.com"
    ) -> dict[str, list[dict]]:
        """
        Look up character meanings from the API.
        Returns a dict mapping characters to lists of meaning dictionaries.
        """
        try:
            response = requests.get(
                f"{base_url}/lookup_meaning",
                params={"chars": chars},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Warning: lookup_meaning returned {response.status_code}")
                return {}
        except Exception as e:
            print(f"Warning: lookup_meaning failed: {e}")
            return {}

    def get_context(text: str, pos: int, context_len: int = 10) -> tuple[str, str]:
        """Get context around a position in text."""
        start = max(0, pos - context_len)
        end = min(len(text), pos + context_len + 1)
        before = text[start:pos]
        after = text[pos + 1 : end]
        return before, after

    def replace_chars(text: str) -> str:
        """Apply character replacements."""
        result = text
        for old, new in CHAR_REPLACEMENTS.items():
            result = result.replace(old, new)
        return result

    def transcribe_to_ipa(
        text: str,
        dictionary: dict,
        choice_cache: dict,
        base_url: str = "https://qieyun-tts.com",
    ) -> str:
        """Transcribe Chinese text to IPA."""
        # Apply character replacements
        normalized = replace_chars(text)

        ipa_parts = []
        pos = 0

        while pos < len(normalized):
            ch = normalized[pos]

            # Skip whitespace and punctuation (keep as-is)
            if re.match(r"\s", ch) or ch in "。，、；：！？":
                ipa_parts.append(ch)
                pos += 1
                continue

            # Look up character in dictionary
            readings = dictionary.get(ch)
            if readings and len(readings) > 0:
                # Check if we have multiple options
                if len(readings) > 1:
                    # Check for special cases first
                    cache_key = ch
                    if ch in SPECIAL_CASES:
                        choice_idx = SPECIAL_CASES[ch]
                        if 0 <= choice_idx < len(readings):
                            transcription = readings[choice_idx][0]
                        else:
                            transcription = readings[0][0]
                        choice_cache[cache_key] = transcription
                    elif cache_key in choice_cache:
                        transcription = choice_cache[cache_key]
                    else:
                        # Prompt user to choose
                        print(
                            f"\nCharacter '{ch}' has {len(readings)} transcription options:"
                        )

                        before_context, after_context = get_context(normalized, pos)
                        context_display = f"{before_context}[{ch}]{after_context}"
                        print(f"Context: {context_display}")

                        meanings_data = lookup_meaning(ch, base_url)
                        char_meanings = meanings_data.get(ch, [])

                        trans_to_meaning = {}
                        for item in char_meanings:
                            trans_to_meaning[item.get("transcription", "")] = item.get(
                                "meaning", ""
                            )

                        for idx, (trans, freq) in enumerate(readings, 1):
                            meaning = trans_to_meaning.get(trans, "")
                            meaning_str = f" - {meaning}" if meaning else ""
                            print(f"  {idx}. {trans} (frequency: {freq}){meaning_str}")

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
                                print(
                                    f"Please enter a number between 1 and {len(readings)}"
                                )
                            except ValueError:
                                print("Please enter a valid number or 'q'")

                        transcription = readings[choice_idx][0]
                        choice_cache[cache_key] = transcription
                else:
                    # Only one option
                    transcription = readings[0][0]
            else:
                # Character not found in dictionary
                print(
                    f"Warning: Character '{ch}' not found in dictionary, keeping as-is"
                )
                transcription = ch

            ipa_parts.append(transcription)
            pos += 1

        return " ".join(ipa_parts)

    return get_context, lookup_meaning, replace_chars, transcribe_to_ipa


@app.cell
def _(
    book_dir,
    dictionary,
    replace_chars,
    transcribe_to_ipa,
    transcripts_dir,
):
    # Chapter titles mapping
    CHAPTER_TITLES = {
        1: "明義第一",
        2: "變數第二",
        3: "算術第三",
        4: "決策第四",
        5: "循環第五",
        6: "行列第六",
        7: "言語第七",
        8: "方術第八",
        9: "府庫第九",
        10: "格物第十",
        11: "克禍第十一",
        12: "圖畫第十二",
        13: "宏略第十三",
    }

    # Find all markdown files in book directory
    chapter_files = sorted(book_dir.glob("*.md"))
    chapter_files = [f for f in chapter_files if f.stem[0].isdigit()]

    print(f"Found {len(chapter_files)} chapter files")

    # Shared choice cache across all titles
    choice_cache = {}

    # Process each chapter title
    for chapter_file in chapter_files:
        # Extract chapter number from filename (e.g., "01 明義第一.md" -> 1)
        chapter_num_str = chapter_file.stem.split()[0]
        chapter_num = int(chapter_num_str)

        # Get title text
        title_text = CHAPTER_TITLES.get(chapter_num)
        if not title_text:
            print(f"Warning: No title found for chapter {chapter_num}, skipping")
            continue

        # Check if transcript already exists
        transcript_filename = f"audio-{chapter_num}.txt"
        transcript_path = transcripts_dir / transcript_filename

        if transcript_path.exists():
            print(f"✓ Transcript already exists (skipped): {transcript_filename}")
            continue

        # Apply character replacements
        text = replace_chars(title_text)

        print(f"Transcribing chapter {chapter_num} title: {title_text}")

        # Transcribe to IPA (pass choice_cache to remember user choices)
        ipa_text = transcribe_to_ipa(text, dictionary, choice_cache)

        # Save transcript
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(ipa_text)

        print(f"✓ Saved transcript: {transcript_filename}")
        print(f"  IPA: {ipa_text}")
    return


if __name__ == "__main__":
    app.run()
