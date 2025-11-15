import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { convertCinixToTUPA } from "transcription-utils";

type SentenceEntry = {
  chinese: string;
  english: string | null;
  transcription: string | null;
  durationInFrames: number;
};

type LineFragment = {
  text: string;
  sentenceIndex: number;
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
  isInlineCode?: boolean;
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
  let inInlineCode = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];

    // Toggle inline code spans on backticks. The backtick characters themselves
    // are not rendered; instead, characters inside the span are marked so that
    // they can be styled (e.g. with a right border) downstream.
    if (char === "`") {
      inInlineCode = !inInlineCode;
      continue;
    }

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
      isInlineCode: inInlineCode,
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

function formatEnglishSentence(text: string): string {
  if (!text) {
    return "";
  }
  if (text.length === 1) {
    return text.toLocaleUpperCase();
  }
  return `${text[0].toLocaleUpperCase()}${text.slice(1)}`;
}

function renderUnderscoreItalics(text: string): React.ReactNode {
  if (!text) {
    return null;
  }

  const segments: React.ReactNode[] = [];
  const italicPattern = /_([^_]+)_/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = italicPattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push(text.slice(lastIndex, match.index));
    }
    segments.push(<em key={`italic-${match.index}`}>{match[1]}</em>);
    lastIndex = italicPattern.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push(text.slice(lastIndex));
  }

  if (segments.length === 0) {
    return text;
  }

  return segments;
}

function computeKeywordMask(text: string): boolean[] {
  if (!text) {
    return [];
  }

  const chars: string[] = [];

  for (const char of text) {
    if (QUOTE_CHARACTERS.has(char) || char === "`") {
      continue;
    }
    chars.push(char);
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

  // Find first non-whitespace character
  const firstNonWhitespaceIndex = chars.findIndex(
    (char) => char.trim().length > 0,
  );
  if (firstNonWhitespaceIndex >= 0 && chars[firstNonWhitespaceIndex] === "若") {
    mask[firstNonWhitespaceIndex] = true;
  }

  // Find last non-whitespace character
  let lastNonWhitespaceIndex = -1;
  for (let i = chars.length - 1; i >= 0; i -= 1) {
    if (chars[i].trim().length > 0) {
      lastNonWhitespaceIndex = i;
      break;
    }
  }
  if (lastNonWhitespaceIndex >= 0 && chars[lastNonWhitespaceIndex] === "者") {
    mask[lastNonWhitespaceIndex] = true;
  }

  return mask;
}

function splitSentencesByTextLines(
  text: string,
  sentences: ReadonlyArray<SentenceEntry>,
): LineFragment[][] | null {
  if (!text || sentences.length === 0) {
    return null;
  }

  const combined = sentences.map((sentence) => sentence.chinese).join("");
  if (combined !== text) {
    return null;
  }

  const sentenceIndexByChar: number[] = [];
  let offset = 0;
  sentences.forEach((sentence, index) => {
    for (let i = 0; i < sentence.chinese.length; i += 1) {
      sentenceIndexByChar[offset + i] = index;
    }
    offset += sentence.chinese.length;
  });

  const lines: LineFragment[][] = [];
  let currentLine: LineFragment[] = [];
  let currentFragment: LineFragment | null = null;

  const flushFragment = () => {
    if (currentFragment && currentFragment.text) {
      currentLine.push(currentFragment);
    }
    currentFragment = null;
  };

  const flushLine = () => {
    flushFragment();
    if (currentLine.length > 0) {
      lines.push(currentLine);
    }
    currentLine = [];
  };

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];

    if (char === "\n") {
      flushLine();
      continue;
    }

    const sentenceIndex = sentenceIndexByChar[i];
    if (typeof sentenceIndex !== "number") {
      return null;
    }

    if (currentFragment && currentFragment.sentenceIndex === sentenceIndex) {
      currentFragment.text += char;
    } else {
      flushFragment();
      currentFragment = { text: char, sentenceIndex };
    }
  }

  flushLine();

  return lines.length > 0 ? lines : null;
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

  const normalizedText = text.replace(/\t/g, "\u00A0");
  const entries = buildQuoteRenderEntries(normalizedText);
  if (entries.length === 0) {
    return null;
  }

  const trailingMarker = options?.trailingMarker ?? null;
  const isCodeBlock = options?.isCodeBlock ?? false;
  const keywordMask = options?.keywordMask;

  // Compute per-character trailing markers so that every "。" is rendered
  // as an absolutely positioned marker attached to the previous character
  // (subsentence-final punctuation), not only the very last one.
  const perCharTrailingMarkers: Array<string | null> = new Array(
    entries.length,
  ).fill(null);
  const hideChar: boolean[] = new Array(entries.length).fill(false);

  // 1) Attach inline "。" to the previous visible (non-whitespace) character
  for (let i = 0; i < entries.length; i += 1) {
    const char = entries[i].char;
    if (char !== "。") {
      continue;
    }

    let target = i - 1;
    while (target >= 0 && entries[target].char.trim().length === 0) {
      target -= 1;
    }

    if (target >= 0) {
      perCharTrailingMarkers[target] =
        (perCharTrailingMarkers[target] ?? "") + char;
      hideChar[i] = true;
    }
  }

  // 2) If a trailingMarker is explicitly provided (e.g. for the final 「。」 that
  // was removed at the Sentence level), attach it to the last non-whitespace char.
  if (trailingMarker) {
    let target = entries.length - 1;
    while (target >= 0 && entries[target].char.trim().length === 0) {
      target -= 1;
    }
    if (target >= 0) {
      perCharTrailingMarkers[target] =
        (perCharTrailingMarkers[target] ?? "") + trailingMarker;
    }
  }

  // Track quote depth to handle nested quotes correctly
  let quoteDepth = 0;

  return entries.map((entry, index) => {
    const prefixString = entry.prefixes.join("");
    const suffixString = entry.suffixes.join("");
    const currentTrailingMarker = perCharTrailingMarkers[index];
    const showTrailingMarker = Boolean(currentTrailingMarker);
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

    if (entry.char === "\n") {
      return <br key={`char-${index}-break`} />;
    }

    const displayChar =
      entry.char === " " || entry.char === "\u00A0" ? "\u00A0" : entry.char;
    const isKeyword = Boolean(keywordMask?.[index]);
    const isInlineCode = entry.isInlineCode === true;

    const charStyle: React.CSSProperties | undefined = (() => {
      const style: React.CSSProperties = {};
      if (!isKeyword && charColor) {
        style.color = charColor;
      }
      if (isInlineCode) {
        //   // In vertical writing mode this visually appears as a horizontal rule
        //   // across the inline-code run, which still reads as a "right border".
        //   style.borderLeft = "2px solid currentColor";
        //   style.paddingLeft = "0em";
        //   // style.marginLeft = "0.08em";
        style.position = "relative";
      }
      return Object.keys(style).length > 0 ? style : undefined;
    })();

    // When rendering the trailing marker(s) (e.g. 「。」), if it belongs to text that is
    // inside quotes in a code block, color it like a string token so it visually
    // matches the quoted content.
    const trailingMarkerStyle =
      showTrailingMarker &&
      currentTrailingMarker &&
      isCodeBlock &&
      isInsideQuote
        ? { color: "var(--color-code-token-string)" }
        : undefined;

    // Hide characters that have been converted into trailing markers on a previous char
    if (hideChar[index]) {
      return null;
    }

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
          {isInlineCode && (
            <span className="border-l-2 border-current absolute left-2 top-0 bottom-0 opacity-80" />
          )}
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
        {showTrailingMarker && currentTrailingMarker ? (
          <span
            className="absolute bottom-0 right-0 text-punctuation pointer-events-none select-none font-normal transform translate-x-[38%] translate-y-[40%] duration-200 ease-in-out"
            style={trailingMarkerStyle}
          >
            {currentTrailingMarker}
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
  trimLeadingLineBreak = false,
}: {
  text: string;
  highlight: boolean;
  isCodeBlock: boolean;
  trimLeadingLineBreak?: boolean;
}) {
  if (!text) {
    return null;
  }

  const textWithoutLeadingBreaks = trimLeadingLineBreak
    ? text.replace(/^\n+/, "")
    : text;
  if (!textWithoutLeadingBreaks) {
    return null;
  }

  // Treat 「。」 at the very end of the sentence as a trailing marker (existing behavior),
  // and also handle 「。」 that appears immediately before closing quotes at the end,
  // e.g. 『……。』 -> render 「。」 as a trailing marker on the last inner character.
  let hasTrailingMarker = textWithoutLeadingBreaks.endsWith("。");
  let content = textWithoutLeadingBreaks;

  if (hasTrailingMarker) {
    content = textWithoutLeadingBreaks.slice(0, -1);
  } else {
    // Match a final 「。」 immediately followed by one or more closing quotes at the end
    // Example: 『……。』 -> groups: [『……', '。', '』']
    const insideQuoteMatch =
      textWithoutLeadingBreaks.match(/^(.*)(。)([」』]+)$/);
    if (insideQuoteMatch) {
      hasTrailingMarker = true;
      // Remove the 「。」 but keep the closing quotes so that the trailing marker
      // is positioned relative to the last inner character, with the quotes still
      // rendered as suffixes on that character.
      content = `${insideQuoteMatch[1]}${insideQuoteMatch[3]}`;
    }
  }

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
  const sentenceLines = useMemo(() => {
    if (!hasSentenceData) {
      return null;
    }
    return splitSentencesByTextLines(text, sentences);
  }, [hasSentenceData, text, sentences]);

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
  const formattedEnglishLine = englishLine
    ? formatEnglishSentence(englishLine)
    : null;
  const englishLineWithItalics = formattedEnglishLine
    ? renderUnderscoreItalics(formattedEnglishLine)
    : null;

  return (
    <AbsoluteFill style={{ opacity }}>
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 flex flex-col w-full h-full px-[40px] py-20 items-center justify-between">
        {transcriptionLine ? (
          <p
            className={`font-ipa tracking-wide font-normal mb-8 text-center w-full text-slate-500 leading-[1.8] m-0 whitespace-pre-line text-balance ${transcriptionLine.length > 100 ? "text-3xl" : "text-4xl"}`}
          >
            [{transcriptionLine}]
          </p>
        ) : null}
        <div
          className="font-[QijiCombo,serif] leading-[1.2] text-start w-max max-w-[1400px] text-black whitespace-pre-line [writing-mode:vertical-rl] [text-orientation:upright] align-middle flex-1 pr-9 h-[600px] min-h-[600px] max-h-[600px]"
          style={
            isCodeBlock
              ? {
                  outline: "4px solid #000",
                  outlineOffset: "16px",
                  fontSize: "60px",
                }
              : {
                  fontSize: "72px",
                }
          }
        >
          <div
            style={{ transform: isCodeBlock ? undefined : "translateY(0.1em)" }}
          >
            {sentenceLines
              ? sentenceLines.map((lineFragments, lineIndex) => (
                  <div key={`line-${lineIndex}`} className="block">
                    {lineFragments.map((fragment, fragmentIndex) => (
                      <Sentence
                        key={`line-${lineIndex}-${fragmentIndex}`}
                        text={fragment.text}
                        highlight={
                          fragment.sentenceIndex === currentSentenceIndex
                        }
                        isCodeBlock={isCodeBlock}
                      />
                    ))}
                  </div>
                ))
              : hasSentenceData
                ? sentences.map((sentence, index) => (
                    <Sentence
                      key={`${index}-${sentence.chinese}`}
                      text={sentence.chinese}
                      highlight={index === currentSentenceIndex}
                      isCodeBlock={isCodeBlock}
                      trimLeadingLineBreak
                    />
                  ))
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
                className={`font-transcription tracking-wide font-normal mt-4 text-center w-full text-slate-500 leading-[1.2] m-0 whitespace-pre-line min-h-20 text-balance ${transcriptionLine.length > 100 ? "text-3xl" : "text-5xl"}`}
              >
                {convertCinixToTUPA(transcriptionLine)}
              </p>
            ) : null}
            {englishLineWithItalics ? (
              <p
                className={`font-serif font-bold leading-[1.8] m-0 whitespace-nowrap min-h-27 flex items-center justify-center ${
                  formattedEnglishLine && formattedEnglishLine.length > 70
                    ? formattedEnglishLine.length > 100
                      ? "text-4xl"
                      : "text-5xl"
                    : "text-6xl"
                }`}
              >
                {englishLineWithItalics}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
