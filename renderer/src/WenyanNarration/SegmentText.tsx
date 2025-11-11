import React from "react";
import { AbsoluteFill } from "remotion";
import { FONT_FAMILY } from "./constants";

const textStyle: React.CSSProperties = {
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
};

export const SegmentText: React.FC<{ readonly text: string }> = ({ text }) => {
  return (
    <AbsoluteFill>
      <div style={textStyle}>{text}</div>
    </AbsoluteFill>
  );
};

