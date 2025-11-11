import { AbsoluteFill, Html5Audio, Sequence, staticFile } from "remotion";
import { loadSegments } from "./loadSegments";
import { SegmentText } from "./WenyanNarration/SegmentText";
import { z } from "zod";

export const wenyanNarrationSchema = z.object({});

const segments = loadSegments();

export const WenyanNarration: React.FC<
  z.infer<typeof wenyanNarrationSchema>
> = () => {
  let currentFrame = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      {segments.map((segment) => {
        const startFrame = currentFrame;
        const durationFrames = segment.durationInFrames;
        currentFrame += durationFrames;

        return (
          <Sequence
            key={segment.id}
            from={startFrame}
            durationInFrames={durationFrames}
          >
            <Html5Audio src={staticFile(segment.audioPath)} />
            <SegmentText text={segment.text} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
