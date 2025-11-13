import React from "react";
import { Series } from "remotion";
import { BookTitle } from "./Intro/BookTitle";
import { WenyanLanguageIntroduction } from "./Intro/WenyanLanguageIntroduction";
import { BookIntroduction } from "./Intro/BookIntroduction";
import { CreatorIntroduction } from "./Intro/CreatorIntroduction";
import { VideoExplanation } from "./Intro/VideoExplanation";

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
    <Series>
      <Series.Sequence durationInFrames={BOOK_TITLE_DURATION_FRAMES}>
        <BookTitle durationInFrames={BOOK_TITLE_DURATION_FRAMES} />
      </Series.Sequence>
      <Series.Sequence
        durationInFrames={WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES}
      >
        <WenyanLanguageIntroduction
          durationInFrames={WENYAN_LANGUAGE_INTRODUCTION_DURATION_FRAMES}
        />
      </Series.Sequence>
      <Series.Sequence durationInFrames={BOOK_INTRODUCTION_DURATION_FRAMES}>
        <BookIntroduction
          durationInFrames={BOOK_INTRODUCTION_DURATION_FRAMES}
        />
      </Series.Sequence>
      <Series.Sequence durationInFrames={CREATOR_INTRODUCTION_DURATION_FRAMES}>
        <CreatorIntroduction
          durationInFrames={CREATOR_INTRODUCTION_DURATION_FRAMES}
        />
      </Series.Sequence>
      <Series.Sequence durationInFrames={VIDEO_EXPLANATION_DURATION_FRAMES}>
        <VideoExplanation
          durationInFrames={VIDEO_EXPLANATION_DURATION_FRAMES}
        />
      </Series.Sequence>
    </Series>
  );
};
