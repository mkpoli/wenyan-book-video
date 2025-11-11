import React from "react";
import { AbsoluteFill } from "remotion";
import { FONT_FAMILY, TRANSLATION_FONT_FAMILY } from "./constants";

interface SegmentTextProps {
  readonly text: string;
  readonly translation: string | null;
}

const originalTextStyle: React.CSSProperties = {
  fontFamily: FONT_FAMILY,
  fontSize: 48,
  lineHeight: 1.8,
  textAlign: "center",
  position: "absolute",
  top: "50%",
  left: "50%",
  transform: "translate(-50%, -50%)",
  width: "80%",
  maxWidth: "1400px",
  color: "#000000",
  padding: "40px",
  whiteSpace: "pre-line",
};

const translationContainer: React.CSSProperties = {
  position: "absolute",
  bottom: 120,
  left: "50%",
  transform: "translateX(-50%)",
  width: "80%",
  maxWidth: "1400px",
  backgroundColor: "rgba(255, 255, 255, 0.75)",
  borderRadius: 16,
  padding: "24px 32px",
  boxShadow: "0 12px 40px rgba(0, 0, 0, 0.12)",
};

const translationTextStyle: React.CSSProperties = {
  fontFamily: TRANSLATION_FONT_FAMILY,
  fontSize: 28,
  lineHeight: 1.6,
  color: "#1b1b1b",
  margin: 0,
  whiteSpace: "pre-line",
  textAlign: "left" as const,
};

export const SegmentText: React.FC<SegmentTextProps> = ({
  text,
  translation,
}) => {
  return (
    <AbsoluteFill>
      <div style={originalTextStyle}>{text}</div>
      {translation ? (
        <div style={translationContainer}>
          <p style={translationTextStyle}>{translation}</p>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

