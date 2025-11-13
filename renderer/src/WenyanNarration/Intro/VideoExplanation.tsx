import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface VideoExplanationProps {
  readonly durationInFrames: number;
}

export const VideoExplanation: React.FC<VideoExplanationProps> = ({
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
        className="flex flex-col items-center justify-center max-w-6xl px-16 gap-8"
        style={{ opacity }}
      >
        <div className="flex flex-col gap-6 w-full items-center">
          <h2 className="font-serif text-5xl font-bold text-gray-900 text-center">
            About This Video
          </h2>
          <h2 className="font-[QijiCombo,serif] text-5xl font-bold text-gray-900 text-center">
            誦《文言陰符》記
          </h2>
          <p className="font-serif text-3xl leading-relaxed text-gray-700 text-center max-w-5xl">
            This video is an attempt to render{" "}
            <span className="italic">The Book</span> aloud through a TTS system
            based on the <span className="italic">Tshet-uinh (Qieyun)</span>{" "}
            Phonological System (Middle Chinese), developed by @cinix, together
            with various other modern technologies.
          </p>
          <p className="font-[QijiCombo,serif] text-4xl leading-relaxed text-gray-900 text-center max-w-5xl">
            是映像也，以　
            <span className="font-transcription text-2xl mr-2 ml-10">
              @cinix
            </span>
            氏所製中古漢語切韻音系語音合成之法，
            <br />
            兼采今時羣工之妙，以誦《文言陰符》，遂成其作。
          </p>
        </div>
      </div>
    </AbsoluteFill>
  );
};
