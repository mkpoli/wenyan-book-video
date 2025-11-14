import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { convertCinixToTUPA } from "transcription-utils";

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
  readonly fadeOutDuration?: number; // Duration in frames for fade-out, undefined means no fade-out
  readonly totalDuration?: number; // Total duration in frames (needed for fade-out calculation)
  readonly isCodeBlock?: boolean;
  readonly showAllCompleted?: boolean; // If true, show all sentences as non-highlighted (completed state)
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

const CHINESE_NUMBERS = new Set([
  "一",
  "二",
  "三",
  "四",
  "五",
  "六",
  "七",
  "八",
  "九",
  "十",
  "百",
  "千",
  "萬",
  "零",
]);

const QUOTE_CHARACTERS = new Set(["「", "」", "『", "』"]);

const KEYWORD_SENTENCES = new Set([
  "若非",
  "也",
  "云云",
  "或若",
  "若其然者",
  "若其不然者",
]);

function computeKeywordMask(text: string): boolean[] {
  if (!text) {
    return [];
  }

  const chars: string[] = [];

  for (const char of text) {
    if (!QUOTE_CHARACTERS.has(char)) {
      chars.push(char);
    }
  }

  if (chars.length === 0) {
    return [];
  }

  const mask = new Array<boolean>(chars.length).fill(false);
  const normalized = chars.join("").trim();

  if (KEYWORD_SENTENCES.has(normalized)) {
    mask.fill(true);
    return mask;
  }

  if (chars[0] === "若") {
    mask[0] = true;
  }

  const lastIndex = chars.length - 1;
  if (chars[lastIndex] === "者") {
    mask[lastIndex] = true;
  }

  return mask;
}

function renderTextWithQuotes(
  text: string,
  options?: {
    trailingMarker?: string | null;
    isCodeBlock?: boolean;
    keywordMask?: ReadonlyArray<boolean>;
  },
): React.ReactNode {
  if (!text) {
    return null;
  }

  const entries = buildQuoteRenderEntries(text);
  if (entries.length === 0) {
    return null;
  }

  const trailingMarker = options?.trailingMarker ?? null;
  const isCodeBlock = options?.isCodeBlock ?? false;
  const keywordMask = options?.keywordMask;

  // Track quote depth to handle nested quotes correctly
  let quoteDepth = 0;

  return entries.map((entry, index) => {
    const prefixString = entry.prefixes.join("");
    const suffixString = entry.suffixes.join("");
    const showTrailingMarker =
      Boolean(trailingMarker) && index === entries.length - 1;
    const isChineseNumber = isCodeBlock && CHINESE_NUMBERS.has(entry.char);

    // Count quote markers in prefixes and suffixes
    const quotePrefixCount =
      (prefixString.match(/「/g)?.length ?? 0) +
      (prefixString.match(/『/g)?.length ?? 0);
    const quoteSuffixCount =
      (suffixString.match(/」/g)?.length ?? 0) +
      (suffixString.match(/』/g)?.length ?? 0);

    // Check if we're currently inside quotes (before processing this character)
    const isInsideQuote = quoteDepth > 0;

    // Update quote depth
    quoteDepth += quotePrefixCount - quoteSuffixCount;

    // Determine color based on code block highlighting rules
    let charColor: string | undefined;
    if (isCodeBlock) {
      if (isInsideQuote || quotePrefixCount > 0) {
        charColor = "var(--color-code-token-string)";
      } else if (isChineseNumber) {
        charColor = "var(--color-code-token-number)";
      }
    }

    const displayChar =
      entry.char === " " || entry.char === "\u00A0" ? "\u00A0" : entry.char;
    const isKeyword = Boolean(keywordMask?.[index]);
    const charStyle =
      !isKeyword && charColor ? { color: charColor } : undefined;

    return (
      <span
        key={`char-${index}-${entry.char}`}
        className="relative inline-block align-middle"
      >
        {prefixString ? (
          <span
            className="absolute left-1/2 text-punctuation pointer-events-none select-none"
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
        <span
          className={isKeyword ? "text-keyword" : undefined}
          style={charStyle}
        >
          {displayChar}
        </span>
        {suffixString ? (
          <span
            className="absolute left-1/2 text-punctuation pointer-events-none select-none"
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
          <span className="absolute bottom-0 right-0 text-punctuation pointer-events-none select-none font-normal transform translate-x-[38%] translate-y-[40%] duration-200 ease-in-out">
            {trailingMarker}
          </span>
        ) : null}
      </span>
    );
  });
}

function Sentence({
  text,
  highlight,
  isCodeBlock,
}: {
  text: string;
  highlight: boolean;
  isCodeBlock: boolean;
}) {
  if (!text) {
    return null;
  }

  const hasTrailingMarker = text.endsWith("。");
  const content = hasTrailingMarker ? text.slice(0, -1) : text;
  const renderedContent = renderTextWithQuotes(content, {
    trailingMarker: hasTrailingMarker ? "。" : null,
    isCodeBlock,
    keywordMask: isCodeBlock ? computeKeywordMask(content) : undefined,
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
  fadeOutDuration,
  totalDuration,
  isCodeBlock = false,
  showAllCompleted = false,
}) => {
  const frame = useCurrentFrame();
  const hasSentenceData = sentences.length > 0;

  // Calculate opacity with fade-in and/or fade-out
  let opacity = 1;

  if (fadeInDuration && fadeOutDuration && totalDuration) {
    // Both fade in and fade out
    const fadeOutStart = totalDuration - fadeOutDuration;
    opacity = interpolate(
      frame,
      [0, fadeInDuration, fadeOutStart, totalDuration],
      [0, 1, 1, 0],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      },
    );
  } else if (fadeInDuration) {
    // Only fade in
    opacity = interpolate(frame, [0, fadeInDuration], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  } else if (fadeOutDuration && totalDuration) {
    // Only fade out - start immediately from frame 0
    opacity = interpolate(frame, [0, fadeOutDuration], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  }

  let cumulative = 0;
  let currentSentenceIndex = -1;

  if (hasSentenceData && !showAllCompleted) {
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
  } else if (showAllCompleted && sentences.length > 0) {
    // Highlight only the last sentence
    currentSentenceIndex = sentences.length - 1;
  }
  // If showAllCompleted is true, currentSentenceIndex stays -1, so no sentence is highlighted

  // For transcription/english display: use current sentence if available, otherwise use last sentence when showing all completed
  const sentenceForDisplay =
    currentSentenceIndex >= 0
      ? sentences[currentSentenceIndex]
      : sentences.length > 0
        ? sentences[sentences.length - 1]
        : null;
  const transcriptionLine =
    sentenceForDisplay?.transcription?.replace(/\s+/g, " ").trim() ?? null;
  const englishLine =
    sentenceForDisplay?.english?.replace(/\s+/g, " ").trim() ?? null;

  // Group sentences by lines when text contains newlines
  const renderSentencesWithLineBreaks = () => {
    if (!hasSentenceData || !text.includes("\n")) {
      // Fallback to original behavior if no newlines
      return sentences.map((sentence, index) => (
        <Sentence
          key={`${index}-${sentence.chinese}`}
          text={sentence.chinese}
          highlight={index === currentSentenceIndex}
          isCodeBlock={isCodeBlock}
        />
      ));
    }

    // Split text by newlines to get lines
    const textLines = text.split("\n").filter((line) => line.trim().length > 0);
    const result: React.ReactNode[] = [];
    let sentenceIndex = 0;

    for (let lineIndex = 0; lineIndex < textLines.length; lineIndex += 1) {
      const line = textLines[lineIndex];
      // Find sentences that belong to this line
      const lineSentences: React.ReactNode[] = [];
      let lineText = "";

      // Collect sentences until we've matched the line content
      while (sentenceIndex < sentences.length) {
        const sentence = sentences[sentenceIndex];
        lineText += sentence.chinese;
        lineSentences.push(
          <Sentence
            key={`${sentenceIndex}-${sentence.chinese}`}
            text={sentence.chinese}
            highlight={sentenceIndex === currentSentenceIndex}
            isCodeBlock={isCodeBlock}
          />,
        );
        sentenceIndex += 1;

        // Check if we've matched the line (allowing for slight variations)
        // Remove all whitespace and compare
        const normalizedLine = line.replace(/\s+/g, "");
        const normalizedLineText = lineText.replace(/\s+/g, "");
        if (normalizedLineText === normalizedLine) {
          break;
        }
        // Safety check: if we've exceeded the line length, break to avoid infinite loop
        if (normalizedLineText.length > normalizedLine.length) {
          break;
        }
      }

      // Render the line with its sentences
      // For vertical writing mode, wrap each line in a block container to create line breaks
      if (lineSentences.length > 0) {
        result.push(
          <div key={`line-${lineIndex}`} className="block">
            {lineSentences}
          </div>,
        );
      }
    }

    // Render any remaining sentences that weren't matched to lines
    while (sentenceIndex < sentences.length) {
      const sentence = sentences[sentenceIndex];
      result.push(
        <Sentence
          key={`${sentenceIndex}-${sentence.chinese}`}
          text={sentence.chinese}
          highlight={sentenceIndex === currentSentenceIndex}
          isCodeBlock={isCodeBlock}
        />,
      );
      sentenceIndex += 1;
    }

    return result;
  };

  return (
    <AbsoluteFill style={{ opacity }}>
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 flex flex-col w-full h-full px-[40px] py-20 items-center justify-between">
        {transcriptionLine ? (
          <p className="font-ipa text-4xl tracking-wide font-normal mb-8 text-center w-full text-slate-500 leading-[1.8] m-0 whitespace-pre-line">
            [{transcriptionLine}]
          </p>
        ) : null}
        <div
          className="font-[QijiCombo,serif] text-[72px] leading-[1.2] text-start w-max max-w-[1400px] text-black whitespace-pre-line [writing-mode:vertical-rl] [text-orientation:upright] align-middle flex-1 pr-9 h-[600px] min-h-[600px] max-h-[600px]"
          style={
            isCodeBlock
              ? { outline: "4px solid #000", outlineOffset: "16px" }
              : undefined
          }
        >
          <div style={{ transform: "translateY(0.1em)" }}>
            {hasSentenceData
              ? renderSentencesWithLineBreaks()
              : renderTextWithQuotes(text, {
                  isCodeBlock,
                  keywordMask: isCodeBlock
                    ? computeKeywordMask(text)
                    : undefined,
                })}
          </div>
        </div>
        {transcriptionLine || englishLine ? (
          <div className="w-3/4 text-center text-slate-900 mt-4">
            {transcriptionLine ? (
              <p
                className={`font-transcription tracking-wide font-normal mt-4 text-center w-full text-slate-500 leading-[1.2] m-0 whitespace-pre-line min-h-20 text-balance ${transcriptionLine.length > 100 ? "text-2xl" : "text-5xl"}`}
              >
                {convertCinixToTUPA(transcriptionLine)}
              </p>
            ) : null}
            {englishLine ? (
              <p
                className={`font-serif font-bold leading-[1.8] m-0 whitespace-nowrap min-h-27 flex items-center justify-center ${
                  englishLine.length > 70
                    ? englishLine.length > 100
                      ? "text-4xl"
                      : "text-5xl"
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
