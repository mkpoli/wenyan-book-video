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

type QuoteRenderEntry = {
  char: string;
  prefixes: string[];
  suffixes: string[];
};

type QuoteStackEntry = {
  opening: "「" | "『";
  closing: "」" | "』";
  firstCharIndex: number | null;
  lastCharIndex: number | null;
};

const OPEN_TO_CLOSE: Record<"「" | "『", "」" | "』"> = {
  "「": "」",
  "『": "』",
};

function buildQuoteRenderEntries(text: string): QuoteRenderEntry[] {
  const entries: QuoteRenderEntry[] = [];
  const stack: QuoteStackEntry[] = [];

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];

    if (char === "「" || char === "『") {
      stack.push({
        opening: char,
        closing: OPEN_TO_CLOSE[char],
        firstCharIndex: null,
        lastCharIndex: null,
      });
      continue;
    }

    if (char === "」" || char === "』") {
      for (let j = stack.length - 1; j >= 0; j -= 1) {
        const quote = stack[j];
        if (quote.closing === char) {
          stack.splice(j, 1);
          if (quote.lastCharIndex !== null) {
            entries[quote.lastCharIndex].suffixes.push(char);
          }
          break;
        }
      }
      continue;
    }

    const entry: QuoteRenderEntry = {
      char,
      prefixes: [],
      suffixes: [],
    };

    stack.forEach((quote) => {
      if (quote.firstCharIndex === null) {
        quote.firstCharIndex = entries.length;
        entry.prefixes.push(quote.opening);
      }
      quote.lastCharIndex = entries.length;
    });

    entries.push(entry);
  }

  return entries;
}

function renderTextWithQuotes(
  text: string,
  options?: { trailingMarker?: string | null },
): React.ReactNode {
  if (!text) {
    return null;
  }

  const entries = buildQuoteRenderEntries(text);
  if (entries.length === 0) {
    return null;
  }

  const trailingMarker = options?.trailingMarker ?? null;

  return entries.map((entry, index) => {
    const prefixString = entry.prefixes.join("");
    const suffixString = entry.suffixes.join("");
    const showTrailingMarker =
      Boolean(trailingMarker) && index === entries.length - 1;

    return (
      <span
        key={`char-${index}-${entry.char}`}
        className="relative inline-block align-middle"
      >
        {prefixString ? (
          <span
            className="absolute left-1/2 text-[#d35835ee] pointer-events-none select-none"
            style={{
              top: 0,
              transform:
                prefixString == "「"
                  ? "translate(-50%, -60%)"
                  : "translate(-40%, -70%)",
            }}
          >
            {prefixString}
          </span>
        ) : null}
        {entry.char}
        {suffixString ? (
          <span
            className="absolute left-1/2 text-[#d35835ee] pointer-events-none select-none"
            style={{
              bottom: 0,
              transform:
                suffixString == "」"
                  ? "translate(-50%, 60%)"
                  : "translate(-60%, 70%)",
            }}
          >
            {suffixString}
          </span>
        ) : null}
        {showTrailingMarker && trailingMarker ? (
          <span className="absolute bottom-0 right-0 text-red-400 pointer-events-none select-none font-normal transform translate-x-[42%] translate-y-[48%] duration-200 ease-in-out">
            {trailingMarker}
          </span>
        ) : null}
      </span>
    );
  });
}

function SentenceWithTrailingMarker({
  text,
  highlight,
}: {
  text: string;
  highlight: boolean;
}) {
  if (!text) {
    return null;
  }

  const hasTrailingMarker = text.endsWith("。");
  const content = hasTrailingMarker ? text.slice(0, -1) : text;
  const renderedContent = renderTextWithQuotes(content, {
    trailingMarker: hasTrailingMarker ? "。" : null,
  });

  if (!renderedContent) {
    return null;
  }

  return (
    <span
      className={`relative inline align-middle ${
        highlight ? "text-gray-900 font-bold" : "text-gray-500 font-normal"
      }`}
    >
      {renderedContent}
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
                  text={sentence.chinese}
                  highlight={index === currentSentenceIndex}
                />
              ))
            : renderTextWithQuotes(text)}
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
                className={`font-serif font-bold leading-[1.8] m-0 whitespace-nowrap min-h-[6.75rem] flex items-center justify-center ${
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
