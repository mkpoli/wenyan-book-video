import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { convertIPAToTranscription } from "../../convert";

type SentenceEntry = {
  chinese: string;
  english: string | null;
  transcription: string | null;
  durationInFrames: number;
};

interface SegmentTextProps {
  readonly text: string;
  readonly sentences: ReadonlyArray<SentenceEntry>;
  readonly fadeInDuration?: number; // Duration in frames for fade-in, undefined means no fade-in
}

function SentenceWithTrailingMarker({
  text,
  highlight,
}: {
  text: string;
  highlight: boolean;
}) {
  if (text.length === 0) {
    return null;
  }

  // Split text into all characters except the last one, and the last character
  const allButLast = text.slice(0, -1);
  const lastChar = text[text.length - 1];

  return (
    <span
      className={`relative inline align-middle ${
        highlight ? "text-gray-900 font-bold" : "text-gray-500 font-normal"
      }`}
    >
      {allButLast}
      <span
        className={`relative inline-block after:content-['。'] after:absolute after:bottom-0 after:right-0 after:translate-x-[42%] after:translate-y-[48%] after:text-red-400 after:pointer-events-none after:select-none after:duration-200 after:ease-in-out after:font-normal`}
      >
        {lastChar}
      </span>
    </span>
  );
}

export const SegmentText: React.FC<SegmentTextProps> = ({
  text,
  sentences,
  fadeInDuration,
}) => {
  const frame = useCurrentFrame();
  const hasSentenceData = sentences.length > 0;

  // Calculate fade-in opacity if fadeInDuration is provided
  const opacity = fadeInDuration
    ? interpolate(frame, [0, fadeInDuration], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

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
  const transcriptionLine =
    currentSentence?.transcription?.replace(/\s+/g, " ").trim() ?? null;
  const englishLine =
    currentSentence?.english?.replace(/\s+/g, " ").trim() ?? null;

  return (
    <AbsoluteFill style={{ opacity }}>
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 flex flex-col w-full h-full px-[40px] py-20 items-center justify-between">
        {transcriptionLine ? (
          <p className="font-ipa text-4xl tracking-wide font-normal mb-8 text-center w-full text-slate-500 leading-[1.8] m-0 whitespace-pre-line">
            [{transcriptionLine}]
          </p>
        ) : null}
        <div className="font-[QijiCombo,serif] text-[72px] leading-[1.2] text-start w-max max-w-[1400px] text-black whitespace-pre-line [writing-mode:vertical-rl] [text-orientation:upright] align-middle flex-1">
          {hasSentenceData
            ? sentences.map((sentence, index) => (
                <SentenceWithTrailingMarker
                  key={`${index}-${sentence.chinese}`}
                  text={sentence.chinese.replace(/。/g, "")}
                  highlight={index === currentSentenceIndex}
                />
              ))
            : text}
        </div>
        {transcriptionLine || englishLine ? (
          <div className="w-3/4 text-center text-slate-900 mt-4">
            {transcriptionLine ? (
              <p
                className={`font-transcription tracking-wide font-normal mb-2 text-center w-full text-slate-500 leading-[1.8] m-0 whitespace-pre-line ${transcriptionLine.length > 100 ? "text-2xl" : "text-5xl"}`}
              >
                {convertIPAToTranscription(transcriptionLine)}
              </p>
            ) : null}
            {englishLine ? (
              <p
                className={`font-serif font-bold leading-[1.8] m-0 whitespace-nowrap ${
                  englishLine.length > 70
                    ? englishLine.length > 100
                      ? "text-2xl"
                      : "text-4xl"
                    : "text-6xl"
                }`}
              >
                {`${englishLine[0].toLocaleUpperCase()}${englishLine.slice(1)}`}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
