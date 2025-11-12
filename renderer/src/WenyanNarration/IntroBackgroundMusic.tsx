import React from "react";
import { Html5Audio, interpolate, staticFile, useCurrentFrame } from "remotion";

interface IntroBackgroundMusicProps {
  readonly durationInFrames: number;
  readonly fadeOutDurationFrames: number;
}

export const IntroBackgroundMusic: React.FC<IntroBackgroundMusicProps> = ({
  durationInFrames,
  fadeOutDurationFrames,
}) => {
  const frame = useCurrentFrame();

  // Fade out volume at the end
  const volume = interpolate(
    frame,
    [durationInFrames - fadeOutDurationFrames, durationInFrames],
    [0.1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  return <Html5Audio src={staticFile("audios/bg.mp3")} volume={volume} loop />;
};
