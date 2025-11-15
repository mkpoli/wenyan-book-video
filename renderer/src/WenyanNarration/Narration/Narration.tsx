import React, { useEffect, useMemo, useRef } from "react";
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

const CLEAN_CHAR_PATTERN = /[「」『』`\s]/g;
const APPROX_SECONDS_PER_CHARACTER = 0.5;
const FALLBACK_TAIL_FRAMES = 12;

type ApproxDuration = {
  readonly frames: number;
  readonly seconds: number;
  readonly charCount: number;
};

const countEffectiveChars = (text: string | null | undefined): number => {
  if (!text) {
    return 0;
  }
  return text.replace(CLEAN_CHAR_PATTERN, "").length;
};

const computeApproxDuration = (segment: Segment, fps: number): ApproxDuration => {
  const charsFromSentences = segment.sentences?.reduce((sum, sentence) => {
    return sum + countEffectiveChars(sentence.chinese);
  }, 0) ?? 0;

  const fallbackChars = charsFromSentences > 0
    ? charsFromSentences
    : countEffectiveChars(segment.text);
  const charCount = Math.max(fallbackChars, 1);
  const seconds = charCount * APPROX_SECONDS_PER_CHARACTER;
  const frames = Math.max(1, Math.ceil(seconds * fps) + FALLBACK_TAIL_FRAMES);

  return { frames, seconds, charCount };
};

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
  const approxDurations = useMemo(() => {
    const entries = new Map<string, ApproxDuration>();
    segments.forEach((segment) => {
      entries.set(segment.id, computeApproxDuration(segment, fps));
    });
    return entries;
  }, [segments, fps]);
  const warnedSegmentsRef = useRef<Set<string>>(new Set());

  const resolveAudioDurationFrames = (segment: Segment): number => {
    if (segment.audioPath) {
      return segment.durationInFrames;
    }
    return approxDurations.get(segment.id)?.frames ?? segment.durationInFrames;
  };

  useEffect(() => {
    segments.forEach((segment) => {
      if (segment.audioPath) {
        return;
      }
      if (warnedSegmentsRef.current.has(segment.id)) {
        return;
      }
      warnedSegmentsRef.current.add(segment.id);
      const approxSeconds = approxDurations.get(segment.id)?.seconds ?? 0;
      console.warn(
        `[Narration] Audio missing for segment ${segment.id}; using ~${approxSeconds.toFixed(
          1,
        )} seconds at 0.5s/character.`,
      );
    });
  }, [segments, approxDurations]);

  let currentFrame = 0;

  // Calculate base segments duration (excluding any tail hold)
  const baseSegmentsDuration = segments.reduce((sum, segment, index) => {
    const audioDurationFrames = resolveAudioDurationFrames(segment);
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
        <Sequence durationInFrames={totalDuration}>
          <Html5Audio
            src={staticFile("audios/bg2.mp3")}
            volume={bgAudioVolume}
            loop
          />
        </Sequence>
      )}
      {segments.map((segment, index) => {
        const segmentStartFrame = currentFrame;
        const audioDurationFrames = resolveAudioDurationFrames(segment);
        const approxInfo = approxDurations.get(segment.id);
        const approxSecondsText = approxInfo
          ? approxInfo.seconds.toFixed(1)
          : (audioDurationFrames / fps).toFixed(1);
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
                {!segment.audioPath && (
                  <div className="absolute inset-x-0 bottom-8 flex justify-center px-6">
                    <div className="max-w-5xl rounded-lg bg-amber-600/80 px-6 py-4 text-center text-3xl font-semibold text-white shadow-lg">
                      Missing narration audio; using ≈{approxSecondsText}s
                      {approxInfo && ` (${approxInfo.charCount} chars × 0.5s)`}
                    </div>
                  </div>
                )}
              </AbsoluteFill>
            )}
            {/* Audio plays only for its original duration */}
            {segment.audioPath && (
              <Sequence durationInFrames={audioDurationFrames}>
                <Html5Audio src={staticFile(segment.audioPath)} />
              </Sequence>
            )}
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
