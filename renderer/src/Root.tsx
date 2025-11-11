import "./index.css";
import { Composition } from "remotion";
import { HelloWorld, myCompSchema } from "./HelloWorld";
import { loadSegments } from "./loadSegments";

// Each <Composition> is an entry in the sidebar!

const segments = loadSegments();
const DEFAULT_DURATION_FRAMES = 150;
const totalDuration =
  segments.reduce((sum, segment) => sum + segment.durationInFrames, 0) ||
  DEFAULT_DURATION_FRAMES;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        // You can take the "id" to render a video:
        // npx remotion render HelloWorld
        id="HelloWorld"
        component={HelloWorld}
        durationInFrames={totalDuration || 150}
        fps={30}
        width={1920}
        height={1080}
        // You can override these props for each render:
        // https://www.remotion.dev/docs/parametrized-rendering
        schema={myCompSchema}
        defaultProps={{}}
      />
    </>
  );
};
