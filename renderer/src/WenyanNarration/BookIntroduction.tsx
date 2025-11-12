import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface BookIntroductionProps {
  readonly durationInFrames: number;
}

export const BookIntroduction: React.FC<BookIntroductionProps> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Classical fade in/out
  const fadeInDuration = fps * 1.0; // 1 second
  const fadeOutDuration = fps * 1.0; // 1 second
  const visibleDuration = durationInFrames - fadeInDuration - fadeOutDuration;

  const opacity = interpolate(
    frame,
    [0, fadeInDuration, fadeInDuration + visibleDuration, durationInFrames],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  return (
    <AbsoluteFill className="bg-white flex items-center justify-center">
      <div
        className="flex flex-col items-center justify-center max-w-6xl px-16 gap-10"
        style={{ opacity }}
      >
        <Img
          src={staticFile("images/cover-alt.png")}
          className="max-h-[600px] object-contain mb-4"
        />
        <div className="flex flex-col gap-6 w-full items-center">
          <h2 className="font-serif text-5xl font-bold text-gray-900 text-center w-full whitespace-nowrap">
            An Introduction to Programming in Wenyan Language
          </h2>
          <p className="font-serif text-3xl leading-relaxed text-gray-700 text-center max-w-4xl">
            The official wenyan-lang handbook, written in Classical Chinese.
          </p>
          <p className="font-[QijiCombo,serif] text-4xl leading-relaxed text-gray-900 text-center max-w-4xl">
            《文言陰符》者，「文言」語言津逮之書也。全文以漢文成。
          </p>
        </div>
      </div>
    </AbsoluteFill>
  );
};
