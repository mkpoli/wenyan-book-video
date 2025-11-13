import React from "react";
import { AbsoluteFill, Series } from "remotion";
import { loadSegments } from "./loadSegments";
import { Intro, INTRO_DURATION_FRAMES } from "./WenyanNarration/Intro/Intro";
import {
  ChapterTitle,
  CHAPTER_TITLE_DURATION_FRAMES,
} from "./WenyanNarration/ChapterTitle";
import { Narration } from "./WenyanNarration/Narration/Narration";
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

  // Calculate narration duration from segments
  const narrationDuration = segments.reduce((sum, segment, index) => {
    const audioDurationFrames = segment.durationInFrames;
    const visualDurationFrames =
      audioDurationFrames +
      (index < segments.length - 1 ? DELAY_BETWEEN_SEGMENTS_FRAMES : 0);
    return sum + visualDurationFrames;
  }, 0);

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      <Series>
        {shouldShowTitle && (
          <Series.Sequence durationInFrames={INTRO_DURATION_FRAMES}>
            <Intro fadeOutDurationFrames={INTRO_BG_FADE_OUT_FRAMES} />
          </Series.Sequence>
        )}
        {shouldShowTitle && (
          <Series.Sequence durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}>
            <ChapterTitle
              chapterNumber={chapterNumber!}
              durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}
            />
          </Series.Sequence>
        )}
        <Series.Sequence durationInFrames={narrationDuration}>
          <Narration
            segments={segments}
            startFrame={0}
            shouldShowTitle={shouldShowTitle}
            delayBetweenSegmentsFrames={DELAY_BETWEEN_SEGMENTS_FRAMES}
            transitionFadeInFrames={TRANSITION_FADE_IN_FRAMES}
          />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
