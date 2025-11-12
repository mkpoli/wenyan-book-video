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
    transcripts_dir = Path("../renderer/public/transcripts")
    audios_dir = Path("../renderer/public/audios")

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

    # Find all title transcript files (audio-{chapterNumber}.txt)
    transcript_files = []
    for chapter_num in sorted(CHAPTER_TITLES.keys()):
        transcript_filename = f"audio-{chapter_num}.txt"
        transcript_path = transcripts_dir / transcript_filename
        if transcript_path.exists():
            transcript_files.append((chapter_num, transcript_path))
        else:
            print(f"⚠ Transcript not found: {transcript_filename}")

    print(f"Found {len(transcript_files)} title transcript files")

    # Process each transcript
    for chapter_num, transcript_file in transcript_files:
        # Check if audio already exists
        audio_filename = f"audio-{chapter_num}.mp3"
        audio_path = audios_dir / audio_filename

        if audio_path.exists():
            print(f"✓ Audio already exists: {audio_filename}")
            continue

        # Read IPA transcript
        with open(transcript_file, "r", encoding="utf-8") as f:
            ipa_text = f.read().strip()

        title_text = CHAPTER_TITLES.get(chapter_num, "")
        print(f"Processing chapter {chapter_num} title: {title_text}")
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
            if (chapter_num, transcript_file) != transcript_files[-1]:
                print(f"  Waiting {API_DELAY_SECONDS} seconds before next request...")
                time.sleep(API_DELAY_SECONDS)

        except Exception as e:
            print(f"✗ Error processing {transcript_file.name}: {e}")
            # Still wait to avoid rapid retries
            if (chapter_num, transcript_file) != transcript_files[-1]:
                time.sleep(API_DELAY_SECONDS)
    return


if __name__ == "__main__":
    app.run()
