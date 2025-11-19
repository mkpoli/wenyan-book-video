'use client';

import { useMemo } from 'react';
import type { Sentence, ChapterSentences } from '../api/sentences/[chapterId]/route';
import type { Segment, ChapterSegments } from './SegmentsLoader';

interface SegmentPreviewProps {
  sentences: ChapterSentences | null;
  segments: ChapterSegments | null;
  selectedSegmentId: string | null;
}

type QuoteRenderEntry = {
  char: string;
  prefixes: string[];
  suffixes: string[];
  isInlineCode?: boolean;
};

type QuoteStackEntry = {
  opening: '「' | '『';
  closing: '」' | '』';
  firstCharIndex: number | null;
  lastCharIndex: number | null;
};

const OPEN_TO_CLOSE: Record<'「' | '『', '」' | '』'> = {
  '「': '」',
  '『': '』',
};

const CHINESE_NUMBERS = new Set(['一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '百', '千', '萬', '零']);

const QUOTE_CHARACTERS = new Set(['「', '」', '『', '』']);

function buildQuoteRenderEntries(text: string): QuoteRenderEntry[] {
  const entries: QuoteRenderEntry[] = [];
  const stack: QuoteStackEntry[] = [];
  let inInlineCode = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];

    // Toggle inline code spans on backticks. The backtick characters themselves
    // are not rendered; instead, characters inside the span are marked so that
    // they can be styled (e.g. with a right border) downstream.
    if (char === '`') {
      inInlineCode = !inInlineCode;
      continue;
    }

    if (char === '「' || char === '『') {
      stack.push({
        opening: char,
        closing: OPEN_TO_CLOSE[char],
        firstCharIndex: null,
        lastCharIndex: null,
      });
      continue;
    }

    if (char === '」' || char === '』') {
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

function computeKeywordMask(text: string): boolean[] {
  if (!text) {
    return [];
  }

  const chars: string[] = [];

  for (const char of text) {
    if (QUOTE_CHARACTERS.has(char) || char === '`') {
      continue;
    }
    chars.push(char);
  }

  if (chars.length === 0) {
    return [];
  }

  const mask = new Array<boolean>(chars.length).fill(false);
  const normalized = chars.join('').trim();

  if (
    normalized === '若非' ||
    normalized === '也' ||
    normalized === '云云' ||
    normalized === '或若' ||
    normalized === '若其然者' ||
    normalized === '若其不然者'
  ) {
    mask.fill(true);
    return mask;
  }

  // Find first non-whitespace character
  const firstNonWhitespaceIndex = chars.findIndex((char) => char.trim().length > 0);
  if (firstNonWhitespaceIndex >= 0 && chars[firstNonWhitespaceIndex] === '若') {
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
  if (lastNonWhitespaceIndex >= 0 && chars[lastNonWhitespaceIndex] === '者') {
    mask[lastNonWhitespaceIndex] = true;
  }

  return mask;
}

function renderTextWithQuotes(
  text: string,
  options?: {
    trailingMarker?: string | null;
    isCodeBlock?: boolean;
    keywordMask?: ReadonlyArray<boolean>;
  }
): React.ReactNode {
  if (!text) {
    return null;
  }

  const normalizedText = text.replace(/\t/g, '\u00A0');
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
  const perCharTrailingMarkers: Array<string | null> = new Array(entries.length).fill(null);
  const hideChar: boolean[] = new Array(entries.length).fill(false);

  // 1) Attach inline "。" to the previous visible (non-whitespace) character
  for (let i = 0; i < entries.length; i += 1) {
    const char = entries[i].char;
    if (char !== '。') {
      continue;
    }

    let target = i - 1;
    while (target >= 0 && entries[target].char.trim().length === 0) {
      target -= 1;
    }

    if (target >= 0) {
      perCharTrailingMarkers[target] = (perCharTrailingMarkers[target] ?? '') + char;
      // Transfer any suffixes from the "。" entry to the target entry
      // (e.g., if "。" has a "』" suffix, it should be preserved)
      if (entries[i].suffixes.length > 0) {
        entries[target].suffixes.push(...entries[i].suffixes);
      }
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
      perCharTrailingMarkers[target] = (perCharTrailingMarkers[target] ?? '') + trailingMarker;
    }
  }

  // Track quote depth to handle nested quotes correctly
  let quoteDepth = 0;

  return entries.map((entry, index) => {
    const prefixString = entry.prefixes.join('');
    const suffixString = entry.suffixes.join('');
    const currentTrailingMarker = perCharTrailingMarkers[index];
    const showTrailingMarker = Boolean(currentTrailingMarker);
    const isChineseNumber = isCodeBlock && CHINESE_NUMBERS.has(entry.char);

    // Count quote markers in prefixes and suffixes
    const quotePrefixCount = (prefixString.match(/「/g)?.length ?? 0) + (prefixString.match(/『/g)?.length ?? 0);
    const quoteSuffixCount = (suffixString.match(/」/g)?.length ?? 0) + (suffixString.match(/』/g)?.length ?? 0);

    // Check if we're currently inside quotes (before processing this character)
    const isInsideQuote = quoteDepth > 0;

    // Update quote depth
    quoteDepth += quotePrefixCount - quoteSuffixCount;

    // Determine color based on code block highlighting rules
    let charColor: string | undefined;
    if (isCodeBlock) {
      if (isInsideQuote || quotePrefixCount > 0) {
        charColor = 'var(--color-code-token-string)';
      } else if (isChineseNumber) {
        charColor = 'var(--color-code-token-number)';
      }
    }

    if (entry.char === '\n') {
      return <br key={`char-${index}-break`} />;
    }

    const displayChar = entry.char === ' ' || entry.char === '\u00A0' ? '\u00A0' : entry.char;
    const isKeyword = Boolean(keywordMask?.[index]);
    const isInlineCode = entry.isInlineCode === true;

    const charStyle: React.CSSProperties | undefined = (() => {
      const style: React.CSSProperties = {};
      if (!isKeyword && charColor) {
        style.color = charColor;
      }
      if (isInlineCode) {
        style.position = 'relative';
      }
      return Object.keys(style).length > 0 ? style : undefined;
    })();

    // When rendering the trailing marker(s) (e.g. 「。」), if it belongs to text that is
    // inside quotes in a code block, color it like a string token so it visually
    // matches the quoted content.
    const trailingMarkerStyle =
      showTrailingMarker && currentTrailingMarker && isCodeBlock && isInsideQuote
        ? { color: 'var(--color-code-token-string)' }
        : undefined;

    // Hide characters that have been converted into trailing markers on a previous char
    if (hideChar[index]) {
      return null;
    }

    return (
      <span key={`char-${index}-${entry.char}`} className="relative inline-block align-middle">
        {prefixString ? (
          <span
            className="absolute left-1/2 text-punctuation pointer-events-none select-none"
            style={{
              top: 0,
              transform: prefixString == '「' ? 'translate(-50%, -60%)' : 'translate(-40%, -70%)',
            }}
          >
            {prefixString}
          </span>
        ) : null}
        <span className={isKeyword ? 'text-keyword' : undefined} style={charStyle}>
          {displayChar}
          {isInlineCode && <span className="border-l-2 border-current absolute left-2 top-0 bottom-0 opacity-80" />}
        </span>
        {suffixString ? (
          <span
            className="absolute left-1/2 text-punctuation pointer-events-none select-none"
            style={{
              bottom: 0,
              transform: suffixString == '」' ? 'translate(-50%, 60%)' : 'translate(-60%, 70%)',
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

export default function SegmentPreview({ sentences, segments, selectedSegmentId }: SegmentPreviewProps) {
  const selectedSegment = useMemo(() => {
    if (!segments || !selectedSegmentId) return null;
    return segments.segments.find((s) => s.id === selectedSegmentId) || null;
  }, [segments, selectedSegmentId]);

  const segmentSentences = useMemo(() => {
    if (!selectedSegment || !sentences) return [];
    return sentences.sentences.filter((s) => selectedSegment.sentenceIds.includes(s.id));
  }, [selectedSegment, sentences]);

  const segmentText = useMemo(() => {
    return segmentSentences.map((s) => s.source).join('');
  }, [segmentSentences]);

  // Process segment text similar to Sentence component - handle trailing markers
  const processedText = useMemo(() => {
    if (!segmentText) return { content: '', hasTrailingMarker: false };

    // Treat 「。」 at the very end as a trailing marker
    let hasTrailingMarker = segmentText.endsWith('。');
    let content = segmentText;

    if (hasTrailingMarker) {
      content = segmentText.slice(0, -1);
    } else {
      // Match a final 「。」 immediately followed by one or more closing quotes at the end
      // Example: 『……。』 -> groups: [『……', '。', '』']
      const insideQuoteMatch = segmentText.match(/^(.*)(。)([」』]+)$/);
      if (insideQuoteMatch) {
        hasTrailingMarker = true;
        // Remove the 「。」 but keep the closing quotes
        content = `${insideQuoteMatch[1]}${insideQuoteMatch[3]}`;
      }
    }

    return { content, hasTrailingMarker };
  }, [segmentText]);

  if (!selectedSegment || !sentences || segmentSentences.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500 text-sm">Select a segment to preview</div>
    );
  }

  const renderedContent = renderTextWithQuotes(processedText.content, {
    trailingMarker: processedText.hasTrailingMarker ? '。' : null,
    isCodeBlock: selectedSegment.isCodeBlock,
    keywordMask: selectedSegment.isCodeBlock ? computeKeywordMask(processedText.content) : undefined,
  });

  return (
    <div className="h-full bg-white dark:bg-black">
      <div className="flex flex-col h-full">
        {/* Segment header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-800 shrink-0">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Segment {selectedSegment.id}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {segmentSentences.length} sentence{segmentSentences.length !== 1 ? 's' : ''}
            {selectedSegment.isCodeBlock && ' • Code block'}
            {selectedSegment.isListItem && ' • List item'}
          </p>
        </div>

        {/* Preview - rendered Chinese text */}
        <div className="flex-1 flex items-center justify-center p-4 min-h-0">
          <div
            className={`font-[QijiCombo,serif] h-80 leading-[1.2] text-start text-white whitespace-pre-line overflow-hidden [writing-mode:vertical-rl] [text-orientation:upright] flex items-center justify-center ${
              selectedSegment.isCodeBlock ? 'text-3xl outline-2 outline-black outline-offset-4 p-4' : 'text-4xl'
            }`}
            style={{
              maxWidth: '100%',
            }}
          >
            <div style={{ transform: selectedSegment.isCodeBlock ? undefined : 'translateY(0.1em)' }}>
              {renderedContent || null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
