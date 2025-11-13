import React from "react";
import { Html5Audio, Sequence, staticFile } from "remotion";
import { Segment } from "../generated/segments";
import { SegmentText } from "./SegmentText";

interface NarrationProps {
  readonly segments: readonly Segment[];
  readonly startFrame: number;
  readonly shouldShowTitle: boolean;
  readonly delayBetweenSegmentsFrames: number;
  readonly transitionFadeInFrames: number;
}

export const Narration: React.FC<NarrationProps> = ({
  segments,
  startFrame,
  shouldShowTitle,
  delayBetweenSegmentsFrames,
  transitionFadeInFrames,
}) => {
  let currentFrame = startFrame;

  // Calculate segments duration (excluding chapter title)
  const segmentsDuration = segments.reduce((sum, segment, index) => {
    const audioDurationFrames = segment.durationInFrames;
    const visualDurationFrames =
      audioDurationFrames +
      (index < segments.length - 1 ? delayBetweenSegmentsFrames : 0);
    return sum + visualDurationFrames;
  }, 0);

  return (
    <>
      {/* Background music for reading segments - bg2.mp3 (starts with first segment) */}
      {shouldShowTitle && segmentsDuration > 0 && (
        <Sequence from={startFrame} durationInFrames={segmentsDuration}>
          <Html5Audio src={staticFile("audios/bg2.mp3")} volume={0.02} loop />
        </Sequence>
      )}
      {segments.map((segment, index) => {
        const segmentStartFrame = currentFrame;
        const audioDurationFrames = segment.durationInFrames;
        // Visuals stay visible longer: audio duration + delay (except for last segment)
        const visualDurationFrames =
          audioDurationFrames +
          (index < segments.length - 1 ? delayBetweenSegmentsFrames : 0);

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
                  ? transitionFadeInFrames
                  : undefined
              }
            />
          </Sequence>
        );
      })}
    </>
  );
};
