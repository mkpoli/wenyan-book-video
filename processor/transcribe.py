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

    def transcribe_to_ipa(text, dictionary):
        """Transcribe Chinese text to IPA string."""
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
                    # Use the top (highest frequency) transcription
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
    segment_files = sorted(segments_dir.glob("*.txt"))

    print(f"Found {len(segment_files)} segment files")

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

        # Transcribe to IPA
        ipa_text = transcribe_to_ipa(text, dictionary)

        # Save transcript
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(ipa_text)

        print(f"✓ Saved transcript: {transcript_filename}")
        print(f"  IPA: {ipa_text[:100]}...")
    return


if __name__ == "__main__":
    app.run()
