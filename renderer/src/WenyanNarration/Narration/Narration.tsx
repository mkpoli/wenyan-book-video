import React from "react";
import {
  Html5Audio,
  Sequence,
  staticFile,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  AbsoluteFill,
  useRemotionEnvironment,
} from "remotion";
import { Segment } from "../../generated/segments";
import { SegmentText } from "./SegmentText";

interface NarrationProps {
  readonly segments: readonly Segment[];
  readonly startFrame: number;
  readonly delayBetweenSegmentsFrames: number;
  readonly transitionFadeInFrames: number;
  readonly tailHoldFrames?: number;
  readonly bgFadeOutFrames?: number;
  readonly tailFadeOutFrames?: number;
  readonly bgVolume?: number;
}

export const Narration: React.FC<NarrationProps> = ({
  segments,
  delayBetweenSegmentsFrames,
  transitionFadeInFrames,
  tailHoldFrames = 0,
  bgFadeOutFrames,
  tailFadeOutFrames,
  bgVolume = 0.02,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  let currentFrame = 0;

  // Calculate base segments duration (excluding any tail hold)
  const baseSegmentsDuration = segments.reduce((sum, segment, index) => {
    const audioDurationFrames = segment.durationInFrames;
    const visualDurationFrames =
      audioDurationFrames +
      (index < segments.length - 1 ? delayBetweenSegmentsFrames : 0);
    return sum + visualDurationFrames;
  }, 0);

  const tailFrames = Math.max(0, tailHoldFrames);
  const totalDuration = baseSegmentsDuration + tailFrames;

  const fadeOutFrames =
    typeof bgFadeOutFrames === "number" ? bgFadeOutFrames : fps * 2.5; // More gradual fade out
  const audioFadeStart = Math.max(0, totalDuration - fadeOutFrames);

  const bgAudioVolume =
    totalDuration > 0
      ? interpolate(
          frame,
          [0, audioFadeStart, totalDuration],
          [bgVolume, bgVolume, 0],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          },
        )
      : 0;

  const { isStudio } = useRemotionEnvironment();
  return (
    <>
      {/* Background music for reading segments - bg2.mp3 (starts with first segment) */}
      {totalDuration > 0 && (
        <Sequence from={0} durationInFrames={totalDuration}>
          <Html5Audio
            src={staticFile("audios/bg2.mp3")}
            volume={bgAudioVolume}
            loop
          />
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
            {isStudio && (
              <AbsoluteFill>
                <div className="absolute top-0 right-0 text-8xl">
                  <p>Segment {segment.id}</p>
                </div>
              </AbsoluteFill>
            )}
            {/* Audio plays only for its original duration */}
            <Sequence from={0} durationInFrames={audioDurationFrames}>
              <Html5Audio src={staticFile(segment.audioPath)} />
            </Sequence>
            {/* Visuals persist for the full duration including delay */}
            <SegmentText
              text={segment.text}
              sentences={segment.sentences ?? []}
              fadeInDuration={index === 0 ? transitionFadeInFrames : undefined}
              isCodeBlock={segment.isCodeBlock}
            />
          </Sequence>
        );
      })}
      {/* Hold on the last frame for a bit longer, if requested */}
      {tailFrames > 0 && segments.length > 0 && (
        <Sequence from={baseSegmentsDuration} durationInFrames={tailFrames}>
          <SegmentText
            text={segments[segments.length - 1].text}
            sentences={segments[segments.length - 1].sentences ?? []}
            isCodeBlock={segments[segments.length - 1].isCodeBlock}
            fadeOutDuration={tailFadeOutFrames}
            totalDuration={tailFrames}
            showAllCompleted={true}
          />
        </Sequence>
      )}
    </>
  );
};
