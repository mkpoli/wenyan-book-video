import { AbsoluteFill, Html5Audio, Sequence, staticFile } from "remotion";
import { loadSegments } from "./loadSegments";
import { SegmentText } from "./WenyanNarration/SegmentText";
import { z } from "zod";

export const wenyanNarrationSchema = z.object({});

const segments = loadSegments();
const DELAY_BETWEEN_SEGMENTS_FRAMES = 6;

export const WenyanNarration: React.FC<
  z.infer<typeof wenyanNarrationSchema>
> = () => {
  let currentFrame = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      {segments.map((segment, index) => {
        const startFrame = currentFrame;
        const audioDurationFrames = segment.durationInFrames;
        // Visuals stay visible longer: audio duration + delay (except for last segment)
        const visualDurationFrames =
          audioDurationFrames +
          (index < segments.length - 1 ? DELAY_BETWEEN_SEGMENTS_FRAMES : 0);

        currentFrame += visualDurationFrames;

        return (
          <Sequence
            key={segment.id}
            from={startFrame}
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
