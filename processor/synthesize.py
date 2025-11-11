import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import requests
    import time
    import json
    from pathlib import Path

    return Path, json, requests, time


@app.cell
def _(Path):
    transcripts_dir = Path("../transcripts")
    audios_dir = Path("../audios")

    # Ensure audios directory exists
    audios_dir.mkdir(exist_ok=True)

    # API settings
    SYNTHESIZE_URL = "https://qieyun-tts.com/synthesize"
    MODEL_NAME = "廌言v1.1.1494"
    API_DELAY_SECONDS = 60  # Wait 1 minute between API calls

    return (
        API_DELAY_SECONDS,
        MODEL_NAME,
        SYNTHESIZE_URL,
        audios_dir,
        transcripts_dir,
    )


@app.cell
def _(
    API_DELAY_SECONDS,
    MODEL_NAME,
    SYNTHESIZE_URL,
    audios_dir,
    transcripts_dir,
    time,
    requests,
    json,
):
    # Find all transcript files
    # Sort naturally by extracting chapter and segment numbers
    def sort_key(path):
        # Extract numbers from filename like "audio-1-2.txt" -> (1, 2)
        name = path.stem  # "audio-1-2"
        parts = name.split("-")  # ["audio", "1", "2"]
        return (int(parts[1]), int(parts[2]))  # (chapter, segment)

    transcript_files = sorted(transcripts_dir.glob("audio-*.txt"), key=sort_key)

    print(f"Found {len(transcript_files)} transcript files")

    # Process each transcript
    for transcript_file in transcript_files:
        # Check if audio already exists
        # transcript_file is like "audio-1-1.txt", audio should be "audio-1-1.mp3"
        audio_filename = transcript_file.name.replace(".txt", ".mp3")
        audio_path = audios_dir / audio_filename

        if audio_path.exists():
            print(f"✓ Audio already exists: {audio_filename}")
            continue

        # Read IPA transcript
        with open(transcript_file, "r", encoding="utf-8") as f:
            ipa_text = f.read().strip()

        print(f"Processing {transcript_file.name}...")
        print(f"  IPA: {ipa_text[:100]}...")

        # Call synthesis API
        headers = {
            "Content-Type": "application/json",
            "Referer": "https://qieyun-tts.com/home",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        }

        payload = {"text": ipa_text, "model_name": MODEL_NAME}

        try:
            api_response = requests.post(
                SYNTHESIZE_URL, json=payload, headers=headers, timeout=120
            )
            api_response.raise_for_status()

            # Save audio file
            with open(audio_path, "wb") as f:
                f.write(api_response.content)

            print(f"✓ Successfully generated {audio_filename}")

            # Wait before next API call (except for the last one)
            if transcript_file != transcript_files[-1]:
                print(f"  Waiting {API_DELAY_SECONDS} seconds before next request...")
                time.sleep(API_DELAY_SECONDS)

        except Exception as e:
            print(f"✗ Error processing {transcript_file.name}: {e}")
            # Still wait to avoid rapid retries
            if transcript_file != transcript_files[-1]:
                time.sleep(API_DELAY_SECONDS)
    return


if __name__ == "__main__":
    app.run()
