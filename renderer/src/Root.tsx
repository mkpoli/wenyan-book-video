import "./index.css";
import { Composition } from "remotion";
import { WenyanNarration, wenyanNarrationSchema } from "./WenyanNarration";
import { BookTitle } from "./WenyanNarration/BookTitle";
import { loadSegments } from "./loadSegments";

// Each <Composition> is an entry in the sidebar!

const segments = loadSegments();
const DEFAULT_DURATION_FRAMES = 150;
const DELAY_BETWEEN_SEGMENTS_FRAMES = 6;
const CHAPTER_TITLE_DURATION_FRAMES = 90; // 3 seconds at 30fps
const BOOK_TITLE_DURATION_FRAMES = 120; // 4 seconds at 30fps
const WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const BOOK_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const CREATOR_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
const VIDEO_EXPLANATION_DURATION_FRAMES = 240; // 8 seconds at 30fps

// Get unique chapter numbers
const uniqueChapters = new Set(
  segments.map((segment) => parseInt(segment.id.split("-")[0], 10)),
);
const chapterNumbers = Array.from(uniqueChapters).sort((a, b) => a - b);

// Calculate duration for a specific chapter
const calculateChapterDuration = (chapterNumber: number): number => {
  const chapterSegments = segments.filter(
    (segment) => parseInt(segment.id.split("-")[0], 10) === chapterNumber,
  );

  if (chapterSegments.length === 0) {
    return (
      DEFAULT_DURATION_FRAMES +
      BOOK_TITLE_DURATION_FRAMES +
      WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
      BOOK_INTRODUCTION_DURATION_FRAMES +
      CREATOR_INTRODUCTION_DURATION_FRAMES +
      VIDEO_EXPLANATION_DURATION_FRAMES +
      CHAPTER_TITLE_DURATION_FRAMES
    );
  }

  const segmentDuration = chapterSegments.reduce(
    (sum, segment) => sum + segment.durationInFrames,
    0,
  );
  const delaysDuration =
    chapterSegments.length > 0
      ? (chapterSegments.length - 1) * DELAY_BETWEEN_SEGMENTS_FRAMES
      : 0;
  const titleDuration =
    BOOK_TITLE_DURATION_FRAMES +
    WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
    BOOK_INTRODUCTION_DURATION_FRAMES +
    CREATOR_INTRODUCTION_DURATION_FRAMES +
    VIDEO_EXPLANATION_DURATION_FRAMES +
    CHAPTER_TITLE_DURATION_FRAMES;

  return segmentDuration + delaysDuration + titleDuration;
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Book Title Page - appears before all chapters */}
      <Composition
        id="BookTitle"
        component={BookTitle}
        durationInFrames={BOOK_TITLE_DURATION_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {chapterNumbers.map((chapterNumber) => {
        const duration = calculateChapterDuration(chapterNumber);
        return (
          <Composition
            key={`chapter-${chapterNumber}`}
            // You can take the "id" to render a video:
            // npx remotion render WenyanNarration-Chapter1
            id={`WenyanNarration-Chapter${chapterNumber}`}
            component={WenyanNarration}
            durationInFrames={duration}
            fps={30}
            width={1920}
            height={1080}
            // You can override these props for each render:
            // https://www.remotion.dev/docs/parametrized-rendering
            schema={wenyanNarrationSchema}
            defaultProps={{ chapterNumber }}
          />
        );
      })}
    </>
  );
};
