# Processor

## Main Pipeline

1. Use `segment-text.py` to segment the text into smaller chunks to `renderer/public/segments/`
2. Use `transcribe.py` to transcribe segments to IPA and save to `renderer/public/transcripts/`
3. Use `synthesize.py` to generate the audio for each chunk and save into `renderer/public/audios/`
4. Use `voice-change.py` to change the voice of the audio into `renderer/public/audios/female/`
5. Use `video-renderer.py` to render the video into `videos/`

## Chapter Titles Pipeline

1. Use `transcribe-titles.py` to transcribe chapter titles to IPA and save to `renderer/public/transcripts/audio-{chapterNumber}.txt`
2. Use `synthesize-titles.py` to generate audio for chapter titles and save to `renderer/public/audios/audio-{chapterNumber}.mp3`