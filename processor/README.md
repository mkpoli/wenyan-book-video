# Processor

1. Use `segment-text.py` to segment the text into smaller chunks to `renderer/public/segments/`
2. Use `transcribe.py` to transcribe segments to IPA and save to `renderer/public/transcripts/`
3. Use `https://qieyun-tts.com/home` to generate the audio for each chunk and save into `renderer/public/audios/`
4. Use `voice-change.py` to change the voice of the audio into `renderer/public/audios/female/`
5. Use `video-renderer.py` to render the video into `videos/`