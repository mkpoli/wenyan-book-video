from __future__ import annotations

import time
from pathlib import Path
from typing import Dict

import requests

from processor.utils.cli_style import format_metadata_rows, print_warning


SYNTHESIZE_URL = "https://qieyun-tts.com/synthesize"
MODEL_NAME = "廌言v1.1.1494"
API_DELAY_SECONDS = 60

CHAPTER_TITLES: Dict[int, str] = {
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


def synthesize_titles(root: Path) -> None:
    transcripts_dir = root / "renderer" / "public" / "transcripts"
    audios_dir = root / "renderer" / "public" / "audios"
    audios_dir.mkdir(exist_ok=True)

    transcript_files = []
    for chapter_num in sorted(CHAPTER_TITLES):
        transcript_path = transcripts_dir / f"audio-{chapter_num}.txt"
        if transcript_path.exists():
            transcript_files.append((chapter_num, transcript_path))
        else:
            print_warning(
                "Title transcript missing",
                format_metadata_rows(
                    [
                        ("Chapter", str(chapter_num)),
                        ("Transcript", transcript_path.as_posix()),
                    ]
                ),
            )

    if not transcript_files:
        print_warning(
            "No title transcripts found",
            format_metadata_rows([("Directory", transcripts_dir.as_posix())]),
        )
        return

    print(f"Found {len(transcript_files)} title transcript files")

    for idx, (chapter_num, transcript_file) in enumerate(transcript_files):
        audio_filename = f"audio-{chapter_num}.mp3"
        audio_path = audios_dir / audio_filename
        if audio_path.exists():
            print(f"✓ Audio already exists: {audio_filename}")
            continue

        ipa_text = transcript_file.read_text(encoding="utf-8").strip()
        title_text = CHAPTER_TITLES.get(chapter_num, "")
        print(f"Processing chapter {chapter_num} title: {title_text}")
        if not ipa_text:
            print_warning(
                "Empty IPA transcript",
                format_metadata_rows(
                    [
                        ("Chapter", str(chapter_num)),
                        ("Transcript", transcript_file.as_posix()),
                    ]
                ),
            )
            continue

        payload = {"text": ipa_text, "model_name": MODEL_NAME}
        headers = {
            "Content-Type": "application/json",
            "Referer": "https://qieyun-tts.com/home",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        }

        try:
            response = requests.post(
                SYNTHESIZE_URL, json=payload, headers=headers, timeout=120
            )
            response.raise_for_status()
            audio_path.write_bytes(response.content)
            print(f"✓ Successfully generated {audio_filename}")
        except Exception as exc:  # noqa: BLE001
            print_warning(
                "Title synthesis failed",
                format_metadata_rows(
                    [
                        ("Chapter", str(chapter_num)),
                        ("Transcript", transcript_file.as_posix()),
                        ("Error", str(exc)),
                    ]
                ),
            )
        finally:
            if idx < len(transcript_files) - 1:
                print(f"  Waiting {API_DELAY_SECONDS} seconds before next request...")
                time.sleep(API_DELAY_SECONDS)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    synthesize_titles(root)


if __name__ == "__main__":
    main()
