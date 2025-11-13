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

  return (
    <>
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
