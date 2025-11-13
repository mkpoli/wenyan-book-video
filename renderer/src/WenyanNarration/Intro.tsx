import React from "react";
import { Html5Audio, Sequence, staticFile } from "remotion";
import { BookTitle } from "./BookTitle";
import { WenyanLanguageIntroduction } from "./WenyanLanguageIntroduction";
import { BookIntroduction } from "./BookIntroduction";
import { CreatorIntroduction } from "./CreatorIntroduction";
import { VideoExplanation } from "./VideoExplanation";
import { ChapterTitle } from "./ChapterTitle";

type IntroProps = {
  chapterNumber: number;
  bookTitleDurationFrames: number;
  wenyanLanguageIntroductionDurationFrames: number;
  bookIntroductionDurationFrames: number;
  creatorIntroductionDurationFrames: number;
  videoExplanationDurationFrames: number;
  chapterTitleDurationFrames: number;
};

export const Intro: React.FC<IntroProps> = ({
  chapterNumber,
  bookTitleDurationFrames,
  wenyanLanguageIntroductionDurationFrames,
  bookIntroductionDurationFrames,
  creatorIntroductionDurationFrames,
  videoExplanationDurationFrames,
  chapterTitleDurationFrames,
}) => {
  return (
    <>
      <Sequence from={0} durationInFrames={bookTitleDurationFrames}>
        <BookTitle durationInFrames={bookTitleDurationFrames} />
      </Sequence>
      <Sequence
        from={bookTitleDurationFrames}
        durationInFrames={wenyanLanguageIntroductionDurationFrames}
      >
        <WenyanLanguageIntroduction
          durationInFrames={wenyanLanguageIntroductionDurationFrames}
        />
      </Sequence>
      <Sequence
        from={
          bookTitleDurationFrames + wenyanLanguageIntroductionDurationFrames
        }
        durationInFrames={bookIntroductionDurationFrames}
      >
        <BookIntroduction durationInFrames={bookIntroductionDurationFrames} />
      </Sequence>
      <Sequence
        from={
          bookTitleDurationFrames +
          wenyanLanguageIntroductionDurationFrames +
          bookIntroductionDurationFrames
        }
        durationInFrames={creatorIntroductionDurationFrames}
      >
        <CreatorIntroduction
          durationInFrames={creatorIntroductionDurationFrames}
        />
      </Sequence>
      <Sequence
        from={
          bookTitleDurationFrames +
          wenyanLanguageIntroductionDurationFrames +
          bookIntroductionDurationFrames +
          creatorIntroductionDurationFrames
        }
        durationInFrames={videoExplanationDurationFrames}
      >
        <VideoExplanation durationInFrames={videoExplanationDurationFrames} />
      </Sequence>
      <Sequence
        from={
          bookTitleDurationFrames +
          wenyanLanguageIntroductionDurationFrames +
          bookIntroductionDurationFrames +
          creatorIntroductionDurationFrames +
          videoExplanationDurationFrames
        }
        durationInFrames={chapterTitleDurationFrames}
      >
        <Html5Audio src={staticFile(`audios/audio-${chapterNumber}.mp3`)} />
        <ChapterTitle
          chapterNumber={chapterNumber}
          durationInFrames={chapterTitleDurationFrames}
        />
      </Sequence>
    </>
  );
};
