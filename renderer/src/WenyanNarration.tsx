import React from "react";
import { AbsoluteFill, Html5Audio, Sequence, staticFile } from "remotion";
import { loadSegments } from "./loadSegments";
import { SegmentText } from "./WenyanNarration/SegmentText";
import { ChapterTitle } from "./WenyanNarration/ChapterTitle";
import { z } from "zod";

export const wenyanNarrationSchema = z.object({});

const segments = loadSegments();
const DELAY_BETWEEN_SEGMENTS_FRAMES = 6;
const CHAPTER_TITLE_DURATION_FRAMES = 90; // 3 seconds at 30fps

export const WenyanNarration: React.FC<
  z.infer<typeof wenyanNarrationSchema>
> = () => {
  let currentFrame = 0;
  let previousChapter = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      {segments.map((segment, index) => {
        // Extract chapter number from segment ID (e.g., "1-1" -> 1)
        const chapterNumber = parseInt(segment.id.split("-")[0], 10);
        const isNewChapter = chapterNumber !== previousChapter;
        previousChapter = chapterNumber;

        // Add chapter title sequence if this is the first segment of a new chapter
        const titleStartFrame = currentFrame;
        if (isNewChapter) {
          currentFrame += CHAPTER_TITLE_DURATION_FRAMES;
        }

        const segmentStartFrame = currentFrame;
        const audioDurationFrames = segment.durationInFrames;
        // Visuals stay visible longer: audio duration + delay (except for last segment)
        const visualDurationFrames =
          audioDurationFrames +
          (index < segments.length - 1 ? DELAY_BETWEEN_SEGMENTS_FRAMES : 0);

        currentFrame += visualDurationFrames;

        return (
          <React.Fragment key={segment.id}>
            {/* Chapter title sequence */}
            {isNewChapter && (
              <Sequence
                from={titleStartFrame}
                durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}
              >
                <ChapterTitle
                  chapterNumber={chapterNumber}
                  durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}
                />
              </Sequence>
            )}
            {/* Segment sequence */}
            <Sequence
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
              />
            </Sequence>
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};
