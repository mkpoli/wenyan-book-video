# Processor

## Main Pipeline

1. Use `parse-markdown.py` to parse markdown chapters from `book/` into structured JSON files in `renderer/public/chapters/{chapter}.json`
2. Use `build-sentences.py` to build canonical sentence JSON files in `renderer/public/sentences/{chapter}.sentences.json`
3. Generate required artifacts and adjust them if necessary.
   - Use `segment-text.py` to segment the text from chapter JSON files into smaller chunks to `renderer/public/segments/{chapter}.segments.json`. Check segments if they are appropriate and correct, if not, update the code to regenerate.
   - **Edit segments interactively** using the segmenter web UI: run `bun run dev` in `segmenter/`, select a chapter, hover between sentences to split/merge, then save changes.
   - Use `translate.py` to generate English translations using OpenAI GPT-5 and save to `renderer/public/translations/{chapter}.translations.json`
   - Use `transcribe.py` to interactively transcribe sentences to IPA/TUPA and save into `renderer/public/transcripts/c{chapter}.transcripts.json`
4.  Use `build-segments.py` to (re)build segment-level IPA transcript files `renderer/public/transcripts/audio-{chapter}-{segment}.txt` from the sentence-level IPA data and the chapter `segments` JSON files. This prepares pronunciation text (with required leading/trailing spaces) for the TTS engine.
5.  Use `synthesize.py` to generate the audio for each chunk and save into `renderer/public/audios/`. You can optionally pass `-c <chapter_number>` to synthesize only a specific chapter (e.g., `uv run python synthesize.py -c 1`).
6.  Use `voice-change.py` to change the voice of the audio into `renderer/public/audios/female/`

## Real-time Segment Preview

While iterating on segmentation logic (for example when tweaking `segment-text.py`), run the renderer watcher so the video preview stays current with every processor change:

- From the repo root, run `bun run watch:segments` inside `renderer/`. This watches sentence, translation, transcript, audio, and segment artifacts produced by the processor. Whenever those files change, it automatically re-runs `scripts/generate-segments.ts`, keeping `renderer/src/generated/segments-*.ts` and the Remotion preview in sync.
- Keep this watcher running while you edit processor outputs so you can immediately scrub through Remotion Studio and confirm how regenerated segments will appear in the final narration.

## Chapter Titles Pipeline

1. Use `transcribe-titles.py` to transcribe chapter titles to IPA and save to `renderer/public/transcripts/audio-{chapterNumber}.txt`
2. Use `synthesize-titles.py` to generate audio for chapter titles and save to `renderer/public/audios/audio-{chapterNumber}.mp3`
