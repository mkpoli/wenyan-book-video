import React from "react";
import { Sequence } from "remotion";
import { BookTitle } from "./BookTitle";
import { WenyanLanguageIntroduction } from "./WenyanLanguageIntroduction";
import { BookIntroduction } from "./BookIntroduction";
import { CreatorIntroduction } from "./CreatorIntroduction";
import { VideoExplanation } from "./VideoExplanation";

export const BOOK_TITLE_DURATION_FRAMES = 120; // 4 seconds at 30fps
export const WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
export const BOOK_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
export const CREATOR_INTRODUCTION_DURATION_FRAMES = 240; // 8 seconds at 30fps
export const VIDEO_EXPLANATION_DURATION_FRAMES = 240; // 8 seconds at 30fps

// Total intro duration (excludes chapter title, which belongs to reading section)
export const INTRO_DURATION_FRAMES =
  BOOK_TITLE_DURATION_FRAMES +
  WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
  BOOK_INTRODUCTION_DURATION_FRAMES +
  CREATOR_INTRODUCTION_DURATION_FRAMES +
  VIDEO_EXPLANATION_DURATION_FRAMES;

export type IntroDurations = {
  bookTitle: number;
  wenyanLanguageIntroduction: number;
  bookIntroduction: number;
  creatorIntroduction: number;
  videoExplanation: number;
};

export const INTRO_DURATIONS: IntroDurations = {
  bookTitle: BOOK_TITLE_DURATION_FRAMES,
  wenyanLanguageIntroduction: WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES,
  bookIntroduction: BOOK_INTRODUCTION_DURATION_FRAMES,
  creatorIntroduction: CREATOR_INTRODUCTION_DURATION_FRAMES,
  videoExplanation: VIDEO_EXPLANATION_DURATION_FRAMES,
};

export const Intro: React.FC = () => {
  return (
    <>
      <Sequence from={0} durationInFrames={BOOK_TITLE_DURATION_FRAMES}>
        <BookTitle durationInFrames={BOOK_TITLE_DURATION_FRAMES} />
      </Sequence>
      <Sequence
        from={BOOK_TITLE_DURATION_FRAMES}
        durationInFrames={WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES}
      >
        <WenyanLanguageIntroduction
          durationInFrames={WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES}
        />
      </Sequence>
      <Sequence
        from={
          BOOK_TITLE_DURATION_FRAMES +
          WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES
        }
        durationInFrames={BOOK_INTRODUCTION_DURATION_FRAMES}
      >
        <BookIntroduction
          durationInFrames={BOOK_INTRODUCTION_DURATION_FRAMES}
        />
      </Sequence>
      <Sequence
        from={
          BOOK_TITLE_DURATION_FRAMES +
          WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
          BOOK_INTRODUCTION_DURATION_FRAMES
        }
        durationInFrames={CREATOR_INTRODUCTION_DURATION_FRAMES}
      >
        <CreatorIntroduction
          durationInFrames={CREATOR_INTRODUCTION_DURATION_FRAMES}
        />
      </Sequence>
      <Sequence
        from={
          BOOK_TITLE_DURATION_FRAMES +
          WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES +
          BOOK_INTRODUCTION_DURATION_FRAMES +
          CREATOR_INTRODUCTION_DURATION_FRAMES
        }
        durationInFrames={VIDEO_EXPLANATION_DURATION_FRAMES}
      >
        <VideoExplanation
          durationInFrames={VIDEO_EXPLANATION_DURATION_FRAMES}
        />
      </Sequence>
    </>
  );
};
