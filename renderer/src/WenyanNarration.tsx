import React from "react";
import { AbsoluteFill, Html5Audio, Sequence, staticFile } from "remotion";
import { loadSegments } from "./loadSegments";
import { Intro, INTRO_DURATION_FRAMES } from "./WenyanNarration/Intro";
import {
  ChapterTitle,
  CHAPTER_TITLE_DURATION_FRAMES,
} from "./WenyanNarration/ChapterTitle";
import { Narration } from "./WenyanNarration/Narration";
import { z } from "zod";

export const wenyanNarrationSchema = z.object({
  chapterNumber: z.number().optional(),
});

const DELAY_BETWEEN_SEGMENTS_FRAMES = 6;
const TRANSITION_FADE_IN_FRAMES = 30; // 1 second at 30fps for fade-in transition
const INTRO_BG_FADE_OUT_FRAMES = 60; // 2 seconds at 30fps for fade-out

export const WenyanNarration: React.FC<
  z.infer<typeof wenyanNarrationSchema>
> = ({ chapterNumber }) => {
  const allSegments = loadSegments();

  // Filter segments by chapter if chapterNumber is provided
  const segments =
    chapterNumber !== undefined
      ? allSegments.filter(
          (segment) => parseInt(segment.id.split("-")[0], 10) === chapterNumber,
        )
      : allSegments;

  // Always show book title, introductions, and chapter title at the start when filtering by chapter
  const shouldShowTitle = chapterNumber !== undefined;
  // Intro duration excludes chapter title (chapter title belongs to reading section)
  const introDuration = shouldShowTitle ? INTRO_DURATION_FRAMES : 0;

  // Chapter title starts the reading section
  const chapterTitleStartFrame = introDuration;
  const readingStartFrame =
    chapterTitleStartFrame + CHAPTER_TITLE_DURATION_FRAMES;

  // Calculate reading segments duration (includes chapter title)
  const readingDuration =
    CHAPTER_TITLE_DURATION_FRAMES +
    segments.reduce((sum, segment, index) => {
      const audioDurationFrames = segment.durationInFrames;
      const visualDurationFrames =
        audioDurationFrames +
        (index < segments.length - 1 ? DELAY_BETWEEN_SEGMENTS_FRAMES : 0);
      return sum + visualDurationFrames;
    }, 0);

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      {/* Background music for reading segments - bg2.mp3 (includes chapter title) */}
      {shouldShowTitle && readingDuration > 0 && (
        <Sequence
          from={chapterTitleStartFrame}
          durationInFrames={readingDuration}
        >
          <Html5Audio src={staticFile("audios/bg2.mp3")} volume={0.02} loop />
        </Sequence>
      )}
      {shouldShowTitle && (
        <Intro fadeOutDurationFrames={INTRO_BG_FADE_OUT_FRAMES} />
      )}
      {/* Chapter Title - appears after intro */}
      {shouldShowTitle && (
        <Sequence
          from={chapterTitleStartFrame}
          durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}
        >
          <Html5Audio src={staticFile(`audios/audio-${chapterNumber}.mp3`)} />
          <ChapterTitle
            chapterNumber={chapterNumber!}
            durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}
          />
        </Sequence>
      )}

      <Narration
        segments={segments}
        startFrame={readingStartFrame}
        shouldShowTitle={shouldShowTitle}
        delayBetweenSegmentsFrames={DELAY_BETWEEN_SEGMENTS_FRAMES}
        transitionFadeInFrames={TRANSITION_FADE_IN_FRAMES}
      />
    </AbsoluteFill>
  );
};
