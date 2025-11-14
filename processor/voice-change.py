import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    from elevenlabs.client import ElevenLabs

    # Load environment variables from .env file
    load_dotenv()

    # Load API key from environment
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    if not ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY environment variable not set")

    # Initialize ElevenLabs client
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    AUDIO_DIR = Path("../renderer/public/audios/")
    return AUDIO_DIR, client


@app.cell
def _(AUDIO_DIR):
    import json

    # Ensure female directory exists
    female_dir = AUDIO_DIR / "female"
    female_dir.mkdir(exist_ok=True)

    # API settings
    MODEL_ID = "eleven_multilingual_sts_v2"  # Speech-to-speech model
    OUTPUT_FORMAT = "mp3_44100_128"
    STABILITY = 0.5  # 50%
    SIMILARITY_BOOST = 0.75  # 75%

    VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"  # Alice

    voice_settings = json.dumps(
        {"stability": STABILITY, "similarity_boost": SIMILARITY_BOOST}
    )
    return MODEL_ID, OUTPUT_FORMAT, VOICE_ID, female_dir, voice_settings


@app.cell
def _(
    AUDIO_DIR,
    MODEL_ID,
    OUTPUT_FORMAT,
    VOICE_ID,
    client,
    female_dir,
    voice_settings,
):
    from io import BytesIO

    # Sort audio files naturally by chapter and segment, e.g. "audio-1-2.mp3"
    def sort_key(path):
        # Extract numbers from filename like "audio-1-2.mp3" -> (1, 2)
        name = path.stem  # "audio-1-2"
        parts = name.split("-")  # ["audio", "1", "2"]
        return (int(parts[1]), int(parts[2]))  # (chapter, segment)

    # Collect and sort files matching audio-*-*.mp3
    audio_files = sorted(AUDIO_DIR.glob("audio-*-*.mp3"), key=sort_key)

    print(f"Found {len(audio_files)} audio files to process")

    for file in audio_files:
        female_file = female_dir / f"{file.stem}-f.mp3"
        if female_file.exists():
            continue
        print(f"Generating {female_file} from {file}...")

        # Read input audio file and convert to BytesIO
        with open(file, "rb") as audio_file:
            audio_data = BytesIO(audio_file.read())

        # Perform speech-to-speech conversion
        try:
            audio_stream = client.speech_to_speech.convert(
                voice_id=VOICE_ID,
                audio=audio_data,
                model_id=MODEL_ID,
                output_format=OUTPUT_FORMAT,
                voice_settings=voice_settings,
            )

            # Convert generator to bytes
            audio_bytes = b"".join(audio_stream)

            # Save the converted audio
            with open(female_file, "wb") as output_file:
                output_file.write(audio_bytes)
            print(f"✓ Successfully generated {female_file}")
        except Exception as e:
            print(f"✗ Error processing {file}: {e}")
    return


if __name__ == "__main__":
    app.run()
