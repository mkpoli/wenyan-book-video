import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface CreatorIntroductionProps {
  readonly durationInFrames: number;
}

export const CreatorIntroduction: React.FC<CreatorIntroductionProps> = ({
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
          <p className="font-[QijiCombo,serif] text-5xl leading-relaxed text-gray-900 text-center max-w-5xl">
            兩者及此書體皆爲　
            <span className="text-blue-500 ml-8">黃令東</span>
            所製，得吉尼斯世界紀錄。
            <br />
            今由開源之士共治之，貢獻者有
            <span className="text-blue-500 text-3xl font-transcription ml-10">
              @antfu
            </span>
            及諸君子。
          </p>
          <p className="font-serif text-3xl leading-relaxed text-gray-700 text-center max-w-5xl">
            Both were created by{" "}
            <span className="text-blue-500">Lingdong Huang</span>, who holds a
            Guinness World Record.
            <br />
            Today they are maintained by the open-source community, with
            contributors including{" "}
            <span className="text-blue-500 text-2xl font-transcription">
              @antfu
            </span>{" "}
            and many others.
          </p>
        </div>
      </div>
    </AbsoluteFill>
  );
};
