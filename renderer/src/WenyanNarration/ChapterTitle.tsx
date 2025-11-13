import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const CHAPTER_TITLE_DURATION_FRAMES = 90; // 3 seconds at 30fps

const CHAPTER_TITLES: Record<number, string> = {
  1: "明義第一",
  2: "變數第二",
  3: "算術第三",
  4: "決策第四",
  5: "循環第五",
  6: "行列第六",
  7: "言語第七",
  8: "方術第八",
  9: "府庫第九",
  10: "格物第十",
  11: "克禍第十一",
  12: "圖畫第十二",
  13: "宏略第十三",
};

interface ChapterTitleProps {
  readonly chapterNumber: number;
  readonly durationInFrames: number;
}

export const ChapterTitle: React.FC<ChapterTitleProps> = ({
  chapterNumber,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const title = CHAPTER_TITLES[chapterNumber] || "";

  // Classical fade in/out with subtle slide
  const fadeInDuration = fps * 0.8; // 0.8 seconds - slower, more elegant
  const fadeOutDuration = fps * 0.8; // 0.8 seconds
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
    <AbsoluteFill
      style={{
        backgroundColor: "white",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          fontFamily: "QijiCombo, serif",
          fontSize: 120,
          fontWeight: "bold",
          color: "#1a1a1a",
          textAlign: "center",
          opacity,
          writingMode: "vertical-rl",
          textOrientation: "upright",
          letterSpacing: "0.1em",
        }}
      >
        {title}
      </div>
    </AbsoluteFill>
  );
};
