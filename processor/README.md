# Processor

## Main Pipeline

1. Use `parse-markdown.py` to parse markdown chapters from `book/` into structured JSON files in `renderer/public/chapters/`
2. Use `segment-text.py` to segment the text from chapter JSON files into smaller chunks to `renderer/public/segments/`
3. Check segments if they are appropriate and correct, if not, update the code to regenerate.
4. Use `translate.py` to generate English translations using OpenAI GPT-5 and save to `renderer/public/translations/`
5. Use `transcribe.py` to transcribe segments to IPA and save to `renderer/public/transcripts/audio-{chapter}-{segment}.txt`
6. Optionally use `migration/convert-segment-transcripts-to-sentences.py` and `build-sentences.py` / `migration/generate_sentence_segments.py` to refine sentence alignment and generate `sentence-segments.ts`
7. Use `build-segments.py` to (re)build segment-level IPA transcript files `audio-{chapter}-{segment}.txt` from the sentence-level IPA data and `sentence-segments.ts`. This prepares pronunciation text (with required leading/trailing spaces) for the TTS engine.
8. Use `synthesize.py` to generate the audio for each chunk and save into `renderer/public/audios/`
9. Use `voice-change.py` to change the voice of the audio into `renderer/public/audios/female/`

## Chapter Titles Pipeline

1. Use `transcribe-titles.py` to transcribe chapter titles to IPA and save to `renderer/public/transcripts/audio-{chapterNumber}.txt`
2. Use `synthesize-titles.py` to generate audio for chapter titles and save to `renderer/public/audios/audio-{chapterNumber}.mp3`