import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { FONT_FAMILY, TRANSLATION_FONT_FAMILY } from "./constants";

interface SegmentTextProps {
  readonly text: string;
  readonly sentences: ReadonlyArray<{
    chinese: string;
    english: string | null;
    durationInFrames: number;
  }>;
}

const originalTextStyle: React.CSSProperties = {
  fontFamily: FONT_FAMILY,
  // fontSize: 48,
  fontSize: 72,
  // lineHeight: 1.8,
  lineHeight: 1.2,
  textAlign: "start",
  position: "absolute",
  top: "45%",
  left: "50%",
  transform: "translate(-50%, -50%)",
  // width: "80%",
  width: "max-content",
  maxWidth: "1400px",
  height: "65%",
  color: "#000000",
  padding: "40px",
  whiteSpace: "pre-line",
  writingMode: "vertical-rl" as const,
  textOrientation: "upright" as const,
  // letterSpacing: "0.15em",
  verticalAlign: "middle",
};

const translationTextStyle: React.CSSProperties = {
  fontFamily: TRANSLATION_FONT_FAMILY,
  fontSize: 28,
  lineHeight: 1.6,
  color: "inherit",
  margin: 0,
  whiteSpace: "pre-line",
  textAlign: "left" as const,
};

const translationLineContainer: React.CSSProperties = {
  position: "absolute",
  bottom: 120,
  left: "50%",
  transform: "translateX(-50%)",
  width: "75%",
  maxWidth: "1200px",
  textAlign: "center",
  color: "#0f172a",
};

export const SegmentText: React.FC<SegmentTextProps> = ({
  text,
  sentences,
}) => {
  const frame = useCurrentFrame();
  const hasSentenceData = sentences.length > 0;

  let cumulative = 0;
  let currentSentenceIndex = -1;

  if (hasSentenceData) {
    for (let i = 0; i < sentences.length; i += 1) {
      const sentence = sentences[i];
      const start = cumulative;
      const end = cumulative + sentence.durationInFrames;
      if (frame >= start && frame < end) {
        currentSentenceIndex = i;
        break;
      }
      cumulative += sentence.durationInFrames;
    }
    if (currentSentenceIndex === -1 && sentences.length > 0) {
      currentSentenceIndex = sentences.length - 1;
    }
  }

  const currentSentence =
    currentSentenceIndex >= 0 ? sentences[currentSentenceIndex] : null;
  const englishLine =
    currentSentence?.english?.replace(/\s+/g, " ").trim() ?? null;

  return (
    <AbsoluteFill>
      <div style={originalTextStyle}>
        {hasSentenceData
          ? sentences.map((sentence, index) => (
              <React.Fragment key={`${index}-${sentence.chinese}`}>
                <span
                  style={{
                    color:
                      index === currentSentenceIndex ? "#111827" : "#6b7280",
                    transition: "color 200ms ease",
                  }}
                  className="after:content-['。'] after:text-red-400 after:transform-[translateX(+50%)_translateY(+50%)] after:bottom-0 after:right-0 after:absolute relative"
                >
                  {sentence.chinese.replace(/。/g, "")}
                </span>
              </React.Fragment>
            ))
          : text}
      </div>
      {englishLine ? (
        <div style={translationLineContainer}>
          <p style={translationTextStyle}>{englishLine}</p>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
