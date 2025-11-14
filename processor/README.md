# Processor

## Main Pipeline

1. Use `parse-markdown.py` to parse markdown chapters from `book/` into structured JSON files in `renderer/public/chapters/`
2. Use `segment-text.py` to segment the text from chapter JSON files into smaller chunks to `renderer/public/segments/`
3. Use `transcribe.py` to transcribe segments to IPA and save to `renderer/public/transcripts/`
4. Use `synthesize.py` to generate the audio for each chunk and save into `renderer/public/audios/`
5. Use `voice-change.py` to change the voice of the audio into `renderer/public/audios/female/`
6. Use `translate.py` to generate English translations using OpenAI GPT-5 and save to `renderer/public/translations/`

## Chapter Titles Pipeline

1. Use `transcribe-titles.py` to transcribe chapter titles to IPA and save to `renderer/public/transcripts/audio-{chapterNumber}.txt`
2. Use `synthesize-titles.py` to generate audio for chapter titles and save to `renderer/public/audios/audio-{chapterNumber}.mp3`