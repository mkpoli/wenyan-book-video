import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface WenyanLanguageIntroductionProps {
  readonly durationInFrames: number;
}

export const WenyanLanguageIntroduction: React.FC<
  WenyanLanguageIntroductionProps
> = ({ durationInFrames }) => {
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
          src={staticFile("images/wenyan.png")}
          className="max-w-[600px] max-h-[600px] object-contain mb-4"
        />
        <div className="flex flex-col gap-6 w-full items-center">
          <h2 className="font-serif text-5xl font-bold text-gray-900 text-center">
            Wenyan Language
          </h2>
          <p className="font-serif text-3xl leading-relaxed text-gray-700 text-center max-w-4xl">
            <span className="text-bold">文言</span>, or{" "}
            <span className="font-serif-emph">wenyan</span>, is an esoteric
            programming language that closely follows the grammar and tone of
            classical Chinese literature.
          </p>
          <p className="font-[QijiCombo,serif] text-4xl leading-relaxed text-gray-900 text-center max-w-4xl">
            「文言」者，漢文風編程語言也。
            <br />
            仿經史子集之體，以古文之法書之，譯後則可運行。
          </p>
        </div>
      </div>
    </AbsoluteFill>
  );
};
