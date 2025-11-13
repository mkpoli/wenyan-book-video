import React from "react";
import { AbsoluteFill, Html5Audio, Sequence, staticFile } from "remotion";
import { loadSegments } from "./loadSegments";
import { SegmentText } from "./WenyanNarration/SegmentText";
import { IntroBackgroundMusic } from "./WenyanNarration/IntroBackgroundMusic";
import { Intro } from "./WenyanNarration/Intro";
import { z } from "zod";

export const wenyanNarrationSchema = z.object({
  chapterNumber: z.number().optional(),
});

const DELAY_BETWEEN_SEGMENTS_FRAMES = 6;
const BOOK_TITLE_DURATION_FRAMES = 120; // 4 seconds at 30fps
const WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const BOOK_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const CREATOR_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const VIDEO_EXPLANATION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const CHAPTER_TITLE_DURATION_FRAMES = 90; // 3 seconds at 30fps
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
  const introDuration = shouldShowTitle
    ? BOOK_TITLE_DURATION_FRAMES +
      WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
      BOOK_INTRODUCTION_DURATION_FRAMES +
      CREATOR_INTRODUCTION_DURATION_FRAMES +
      VIDEO_EXPLANATION_DURATION_FRAMES
    : 0;

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

  let currentFrame = readingStartFrame;

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      {/* Background music for intro - bg.mp3 with fade-out */}
      {shouldShowTitle && introDuration > 0 && (
        <Sequence from={0} durationInFrames={introDuration}>
          <IntroBackgroundMusic
            durationInFrames={introDuration}
            fadeOutDurationFrames={INTRO_BG_FADE_OUT_FRAMES}
          />
        </Sequence>
      )}
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
        <Intro
          chapterNumber={chapterNumber!}
          bookTitleDurationFrames={BOOK_TITLE_DURATION_FRAMES}
          wenyanLanguageIntroductionDurationFrames={
            WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES
          }
          bookIntroductionDurationFrames={BOOK_INTRODUCTION_DURATION_FRAMES}
          creatorIntroductionDurationFrames={
            CREATOR_INTRODUCTION_DURATION_FRAMES
          }
          videoExplanationDurationFrames={VIDEO_EXPLANATION_DURATION_FRAMES}
          chapterTitleDurationFrames={CHAPTER_TITLE_DURATION_FRAMES}
        />
      )}

      {segments.map((segment, index) => {
        const segmentStartFrame = currentFrame;
        const audioDurationFrames = segment.durationInFrames;
        // Visuals stay visible longer: audio duration + delay (except for last segment)
        const visualDurationFrames =
          audioDurationFrames +
          (index < segments.length - 1 ? DELAY_BETWEEN_SEGMENTS_FRAMES : 0);

        currentFrame += visualDurationFrames;

        return (
          <Sequence
            key={segment.id}
            from={segmentStartFrame}
            durationInFrames={visualDurationFrames}
          >
            {/* Audio plays only for its original duration */}
            <Sequence from={0} durationInFrames={audioDurationFrames}>
              <Html5Audio src={staticFile(segment.audioPath)} />
            </Sequence>
            {/* Visuals persist for the full duration including delay */}
            <SegmentText
              text={segment.text}
              sentences={segment.sentences ?? []}
              fadeInDuration={
                shouldShowTitle && index === 0
                  ? TRANSITION_FADE_IN_FRAMES
                  : undefined
              }
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
