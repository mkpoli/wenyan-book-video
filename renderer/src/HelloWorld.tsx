import { AbsoluteFill, Html5Audio, Sequence, staticFile } from "remotion";
import { loadSegments } from "./loadSegments";
import { SegmentText } from "./HelloWorld/SegmentText";
import { z } from "zod";

export const myCompSchema = z.object({});

const segments = loadSegments();

export const HelloWorld: React.FC<z.infer<typeof myCompSchema>> = () => {
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
