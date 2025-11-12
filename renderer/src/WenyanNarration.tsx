import React from "react";
import { AbsoluteFill, Html5Audio, Sequence, staticFile } from "remotion";
import { loadSegments } from "./loadSegments";
import { SegmentText } from "./WenyanNarration/SegmentText";
import { ChapterTitle } from "./WenyanNarration/ChapterTitle";
import { BookTitle } from "./WenyanNarration/BookTitle";
import { WenyanLanguageIntroduction } from "./WenyanNarration/WenyanLanguageIntroduction";
import { BookIntroduction } from "./WenyanNarration/BookIntroduction";
import { CreatorIntroduction } from "./WenyanNarration/CreatorIntroduction";
import { z } from "zod";

export const wenyanNarrationSchema = z.object({
  chapterNumber: z.number().optional(),
});

const DELAY_BETWEEN_SEGMENTS_FRAMES = 6;
const BOOK_TITLE_DURATION_FRAMES = 120; // 4 seconds at 30fps
const WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const BOOK_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const CREATOR_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const CHAPTER_TITLE_DURATION_FRAMES = 90; // 3 seconds at 30fps
const TRANSITION_FADE_IN_FRAMES = 30; // 1 second at 30fps for fade-in transition

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
  let currentFrame = shouldShowTitle
    ? BOOK_TITLE_DURATION_FRAMES +
      WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
      BOOK_INTRODUCTION_DURATION_FRAMES +
      CREATOR_INTRODUCTION_DURATION_FRAMES +
      CHAPTER_TITLE_DURATION_FRAMES
    : 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      {shouldShowTitle && (
        <>
          {/* Book Title Page - appears first */}
          <Sequence from={0} durationInFrames={BOOK_TITLE_DURATION_FRAMES}>
            <BookTitle durationInFrames={BOOK_TITLE_DURATION_FRAMES} />
          </Sequence>
          {/* Wenyan Language Introduction - appears after book title */}
          <Sequence
            from={BOOK_TITLE_DURATION_FRAMES}
            durationInFrames={WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES}
          >
            <WenyanLanguageIntroduction
              durationInFrames={WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES}
            />
          </Sequence>
          {/* Book Introduction - appears after language introduction */}
          <Sequence
            from={
              BOOK_TITLE_DURATION_FRAMES +
              WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES
            }
            durationInFrames={BOOK_INTRODUCTION_DURATION_FRAMES}
          >
            <BookIntroduction
              durationInFrames={BOOK_INTRODUCTION_DURATION_FRAMES}
            />
          </Sequence>
          {/* Creator Introduction - appears after book introduction */}
          <Sequence
            from={
              BOOK_TITLE_DURATION_FRAMES +
              WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
              BOOK_INTRODUCTION_DURATION_FRAMES
            }
            durationInFrames={CREATOR_INTRODUCTION_DURATION_FRAMES}
          >
            <CreatorIntroduction
              durationInFrames={CREATOR_INTRODUCTION_DURATION_FRAMES}
            />
          </Sequence>
          {/* Chapter Title - appears after introductions */}
          <Sequence
            from={
              BOOK_TITLE_DURATION_FRAMES +
              WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
              BOOK_INTRODUCTION_DURATION_FRAMES +
              CREATOR_INTRODUCTION_DURATION_FRAMES
            }
            durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}
          >
            <Html5Audio src={staticFile(`audios/audio-${chapterNumber}.mp3`)} />
            <ChapterTitle
              chapterNumber={chapterNumber!}
              durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}
            />
          </Sequence>
        </>
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
