import React from "react";
import {
  AbsoluteFill,
  Html5Audio,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const OUTRO_DURATION_FRAMES = 380; // 12.66 seconds at 30fps
const AUDIO_START_SECONDS = 4 * 60 + 50; // 4:42 in seconds
const BASE_VOLUME = 0.2;

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Calculate trimBefore in frames: 4:42 = 282 seconds * fps
  const trimBeforeFrames = AUDIO_START_SECONDS * fps;

  const fadeInDuration = fps * 2.5; // Longer fade in
  const fadeOutDuration = fps * 1;
  const emptyDuration = fps * 1;
  const visibleDuration =
    OUTRO_DURATION_FRAMES - fadeInDuration - fadeOutDuration - emptyDuration;
  const fadeOutStart = fadeInDuration + visibleDuration;
  const audioFadeDelay = fps * 0.5;
  const audioFadeDuration = fps * 1.8;
  const audioFadeStart = Math.min(
    fadeOutStart + fadeOutDuration + audioFadeDelay,
    OUTRO_DURATION_FRAMES - audioFadeDuration - 1,
  );
  const audioFadeEnd = Math.min(
    audioFadeStart + audioFadeDuration,
    OUTRO_DURATION_FRAMES - 1,
  );

  const opacity = interpolate(
    frame,
    [
      0,
      fadeInDuration,
      fadeOutStart,
      fadeOutStart + fadeOutDuration,
      OUTRO_DURATION_FRAMES,
    ],
    [0, 1, 1, 0, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  const audioVolume = interpolate(
    frame,
    [
      0,
      fadeInDuration,
      fadeOutStart,
      audioFadeStart,
      audioFadeEnd,
      OUTRO_DURATION_FRAMES,
    ],
    [0, BASE_VOLUME, BASE_VOLUME, BASE_VOLUME, 0, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  return (
    <AbsoluteFill className="bg-white flex items-center justify-center px-16">
      <Html5Audio
        src={staticFile("audios/bg3.mp3")}
        volume={audioVolume}
        trimBefore={trimBeforeFrames}
      />
      <div
        className="flex flex-col items-center justify-center gap-12 text-center"
        style={{ opacity }}
      >
        <p className="[writing-mode:vertical-rl] [text-orientation:upright] font-[QijiCombo,serif] text-[7.4rem] text-gray-900 leading-[1.4] tracking-wide">
          <span className="block">承蒙垂覽</span>
          <span className="block">不勝感荷</span>
          <span className="block">佇候雅評</span>
          <span className="block">期君再來</span>
        </p>
        <div className="flex flex-col items-center gap-6 text-center">
          <p className="font-serif text-6xl text-gray-900">
            With Gratitude for Your Kind Attention
          </p>
          <p className="font-serif text-5xl text-gray-700">
            Should this humble work have pleased you, <br /> pray do subscribe
            or bestow a like for more to come.
          </p>
        </div>
      </div>
    </AbsoluteFill>
  );
};
