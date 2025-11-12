import "./index.css";
import { Composition } from "remotion";
import { WenyanNarration, wenyanNarrationSchema } from "./WenyanNarration";
import { loadSegments } from "./loadSegments";

// Each <Composition> is an entry in the sidebar!

const segments = loadSegments();
const DEFAULT_DURATION_FRAMES = 150;
const DELAY_BETWEEN_SEGMENTS_FRAMES = 30; // 1 second at 30fps
const segmentDuration = segments.reduce(
  (sum, segment) => sum + segment.durationInFrames,
  0,
);
const delaysDuration =
  segments.length > 0
    ? (segments.length - 1) * DELAY_BETWEEN_SEGMENTS_FRAMES
    : 0;
const totalDuration =
  segmentDuration + delaysDuration || DEFAULT_DURATION_FRAMES;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        // You can take the "id" to render a video:
        // npx remotion render WenyanNarration
        id="WenyanNarration"
        component={WenyanNarration}
        durationInFrames={totalDuration || 150}
        fps={30}
        width={1920}
        height={1080}
        // You can override these props for each render:
        // https://www.remotion.dev/docs/parametrized-rendering
        schema={wenyanNarrationSchema}
        defaultProps={{}}
      />
    </>
  );
};
