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
    segments_dir = Path("../segments")
    transcripts_dir = Path("../transcripts")

    # Ensure transcripts directory exists
    transcripts_dir.mkdir(exist_ok=True)
    return segments_dir, transcripts_dir


@app.cell
def _(re):
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
        "有": 0,  # Always use 1st choice (index 0)
    }

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

    def transcribe_to_ipa(text, dictionary, choice_cache=None):
        """Transcribe Chinese text to IPA string.

        Args:
            text: Chinese text to transcribe
            dictionary: Dictionary mapping characters to list of (transcription, frequency) tuples
            choice_cache: Optional dict to cache user choices for characters with multiple readings
                          Characters in SPECIAL_CASES are automatically handled without prompting
        """
        if choice_cache is None:
            choice_cache = {}

        normalized = normalize_text(text)

        # Convert each character to IPA
        ipa_parts = []
        for ch in normalized:
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
                                transcription = readings[choice_idx][0]
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
                            for idx, (trans, freq) in enumerate(readings, 1):
                                print(f"  {idx}. {trans} (frequency: {freq})")

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
