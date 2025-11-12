import React from "react";
import { AbsoluteFill, Html5Audio, Sequence, staticFile } from "remotion";
import { loadSegments } from "./loadSegments";
import { SegmentText } from "./WenyanNarration/SegmentText";
import { ChapterTitle } from "./WenyanNarration/ChapterTitle";
import { z } from "zod";

export const wenyanNarrationSchema = z.object({
  chapterNumber: z.number().optional(),
});

const DELAY_BETWEEN_SEGMENTS_FRAMES = 6;
const CHAPTER_TITLE_DURATION_FRAMES = 90; // 3 seconds at 30fps

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

  // Always show chapter title at the start when filtering by chapter
  const shouldShowTitle = chapterNumber !== undefined;
  let currentFrame = shouldShowTitle ? CHAPTER_TITLE_DURATION_FRAMES : 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      {shouldShowTitle && (
        <Sequence from={0} durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}>
          <Html5Audio src={staticFile(`audios/audio-${chapterNumber}.mp3`)} />
          <ChapterTitle
            chapterNumber={chapterNumber!}
            durationInFrames={CHAPTER_TITLE_DURATION_FRAMES}
          />
        </Sequence>
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
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
