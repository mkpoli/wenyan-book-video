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

export const mainSchema = z.object({
  chapterNumber: z.number().optional(),
});

const DELAY_BETWEEN_SEGMENTS_FRAMES = 6;
const TRANSITION_FADE_IN_FRAMES = 30; // 1 second at 30fps for fade-in transition
const INTRO_BG_FADE_OUT_FRAMES = 60; // 2 seconds at 30fps for fade-out

export const Main: React.FC<z.infer<typeof mainSchema>> = ({
  chapterNumber,
}) => {
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

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
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
