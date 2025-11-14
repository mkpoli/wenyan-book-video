import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
  unlinkSync,
} from "fs";
import { parseFile } from "music-metadata";
import { join, relative } from "path";

const rendererDir = process.env.RENDERER_DIR ?? process.cwd();
const SEGMENTS_DIR = join(rendererDir, "public", "segments");
const AUDIOS_DIR = join(rendererDir, "public", "audios");
const AUDIOS_FEMALE_DIR = join(AUDIOS_DIR, "female");
const TRANSLATIONS_DIR = join(rendererDir, "public", "translations");
const TRANSCRIPTS_DIR = join(rendererDir, "public", "transcripts");
const GENERATED_DIR = join(rendererDir, "src", "generated");
const GENERATED_SEGMENTS_FILE = join(GENERATED_DIR, "segments.ts");
const FPS = 30;
const AUDIO_TAIL_FRAMES = 12;
const DEFAULT_AUDIO_DURATION_SECONDS = 3;

const isDebug = process.env.DEBUG_SEGMENTS === "1";
const debugLog = (...args: unknown[]) => {
  if (isDebug) {
    // eslint-disable-next-line no-console
    console.log("[segments]", ...args);
  }
};

const getAudioDurationInSeconds = async (audioPath: string) => {
  try {
    const metadata = await parseFile(audioPath);
    if (metadata.format.duration) {
      return metadata.format.duration;
    }
  } catch (error) {
    const message =
      error instanceof Error ? error.message : JSON.stringify(error);
    console.warn(
      `[segments] Failed to parse duration for ${audioPath}: ${message}`,
    );
  }

  console.warn(
    `[segments] Falling back to default duration (${DEFAULT_AUDIO_DURATION_SECONDS}s) for ${audioPath}`,
  );
  return DEFAULT_AUDIO_DURATION_SECONDS;
};

const countCharsExcludingQuotes = (text: string): number => {
  return text.replace(/[「」『』]/g, "").length;
};

// Counts Chinese characters relevant for aligning with IPA tokens.
// This excludes whitespace, quotes, and common punctuation so that
// each remaining character should correspond to one IPA token.
const countCharsForTranscriptAlignment = (text: string): number => {
  return text
    .replace(/[「」『』]/g, "")
    .replace(/\s/g, "")
    .replace(/[。，、！？；：,.!"'“”‘’]/g, "").length;
};

const splitChineseSentences = (
  text: string,
  preserveSpaces = false,
): string[] => {
  const sentences: string[] = [];
  let currentSentence = "";
  let insideQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];

    if (char === "『") {
      insideQuotes = true;
      currentSentence += char;
    } else if (char === "』") {
      insideQuotes = false;
      currentSentence += char;
      // Check if previous character was sentence-ending punctuation
      if (i > 0) {
        const prevChar = text[i - 1];
        if (prevChar === "。" || prevChar === "！" || prevChar === "？") {
          // Only split at 。』 if NOT immediately followed by another sentence-ending punctuation
          // (e.g., don't split "。』。" - keep it together)
          const nextChar = i + 1 < text.length ? text[i + 1] : null;
          if (nextChar !== "。" && nextChar !== "！" && nextChar !== "？") {
            // Split at 。』 (period followed by closing quote)
            const processed = preserveSpaces
              ? currentSentence
              : currentSentence.trim();
            if (processed.length > 0) {
              sentences.push(processed);
            }
            currentSentence = "";
          }
        }
      }
    } else if (char === "」") {
      // Always include the closing quote
      currentSentence += char;

      // Look ahead for the next non-whitespace character.
      // If it's 「曰」, we treat this as a sentence boundary so that
      // patterns like `…耶」曰「…耶」` or `…耶」\n曰「…耶」` are split
      // between `」` and `曰`.
      let j = i + 1;
      let nextNonWhitespace: string | null = null;
      while (j < text.length) {
        const lookaheadChar = text[j];
        if (!/\s/.test(lookaheadChar)) {
          nextNonWhitespace = lookaheadChar;
          break;
        }
        j++;
      }

      if (nextNonWhitespace === "曰") {
        const processed = preserveSpaces
          ? currentSentence
          : currentSentence.trim();
        if (processed.length > 0) {
          sentences.push(processed);
        }
        currentSentence = "";
      }
    } else if (
      (char === "。" || char === "！" || char === "？") &&
      !insideQuotes
    ) {
      currentSentence += char;
      const processed = preserveSpaces
        ? currentSentence
        : currentSentence.trim();
      if (processed.length > 0) {
        sentences.push(processed);
      }
      currentSentence = "";
    } else {
      currentSentence += char;
    }
  }

  // Add any remaining text as the last sentence
  const processed = preserveSpaces ? currentSentence : currentSentence.trim();
  if (processed.length > 0) {
    sentences.push(processed);
  }

  return sentences;
};

const splitEnglishSentences = (
  translation: string | null,
  preserveSpaces = false,
): string[] => {
  if (!translation) {
    return [];
  }

  const sentences = translation
    .replace(/\r\n/g, "\n")
    .split(/\n+/)
    .map((line) => (preserveSpaces ? line : line.trim()))
    .filter((line) => line.length > 0);

  return sentences;
};

const splitIPATranscriptions = (
  transcript: string | null,
  chineseSentences: string[],
  preserveSpaces = false,
): string[] => {
  if (!transcript) {
    return [];
  }

  // Tokenize IPA transcript: tokens are either IPA syllables or "." as a
  // sentence boundary marker. There should be no other token types.
  const rawTokens = transcript
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);

  const ipaTokens = rawTokens.filter((token) => token !== ".");
  const totalIpaTokens = ipaTokens.length;

  const charCounts = chineseSentences.map((sentence) =>
    countCharsForTranscriptAlignment(sentence),
  );
  const totalChars = charCounts.reduce((sum, count) => sum + count, 0);

  // If the expected 1:1 mapping between Chinese characters and IPA tokens
  // does not hold, fall back to a simpler sentence-based split to avoid
  // producing obviously wrong alignments.
  if (
    totalChars === 0 ||
    totalIpaTokens === 0 ||
    totalChars !== totalIpaTokens
  ) {
    const normalized = preserveSpaces
      ? transcript
      : transcript.trim().replace(/\s+/g, " ");
    return normalized
      .split(/\s*[\.,]\s*/)
      .map((sentence) => (preserveSpaces ? sentence : sentence.trim()))
      .filter(Boolean);
  }

  const sentences: string[] = [];
  let tokenIndex = 0;

  for (const count of charCounts) {
    if (count <= 0) {
      sentences.push("");
      continue;
    }

    const sentenceTokens = ipaTokens.slice(tokenIndex, tokenIndex + count);
    tokenIndex += count;

    const sentence = preserveSpaces
      ? sentenceTokens.join(" ")
      : sentenceTokens.join(" ").trim();
    sentences.push(sentence);
  }

  return sentences;
};

const ansi = (code: number) => (text: string) => `\x1b[${code}m${text}\x1b[0m`;
const styles = {
  bold: ansi(1),
  dim: ansi(2),
  red: ansi(31),
  yellow: ansi(33),
  cyan: ansi(36),
  gray: ansi(90),
};

const stripAnsi = (text: string) => text.replace(/\x1b\[[0-9;]*m/g, "");
const INNER_DIVIDER_TOKEN = "__INNER_DIVIDER__";
const LINT_LINE_LENGTH = 96;

const toRendererRelative = (absolutePath: string): string => {
  const rel = relative(rendererDir, absolutePath);
  return rel.startsWith("..") ? absolutePath : rel || ".";
};

const formatLintBlock = (title: string, rows: string[]): string => {
  const expandedRows = rows.flatMap((row) => {
    if (row === INNER_DIVIDER_TOKEN) {
      return [row];
    }
    return row.includes("\n") ? row.split("\n") : [row];
  });

  const dividerLength = LINT_LINE_LENGTH;
  const titlePlainLength = stripAnsi(title).length;
  const trailingLength = Math.max(2, dividerLength - (titlePlainLength + 4));
  const headingLine = `${styles.yellow("──")} ${styles.bold(
    title,
  )} ${styles.yellow("─".repeat(trailingLength))}`;
  const bottomLine = styles.yellow("─".repeat(dividerLength));

  const innerDivider = styles.yellow("─".repeat(dividerLength));

  const formatRow = (line: string) => {
    if (line === INNER_DIVIDER_TOKEN) {
      return innerDivider;
    }
    return line.trim().length === 0 ? "" : `  ${line}`;
  };

  const lines = [
    "",
    headingLine,
    ...expandedRows.map(formatRow),
    bottomLine,
    "",
  ].filter((line, index, arr) => {
    if (line !== "") {
      return true;
    }
    const prev = index > 0 ? arr[index - 1] : null;
    return prev !== "";
  });

  return lines.join("\n");
};

const logLintWarning = (title: string, rows: string[]) => {
  console.warn(formatLintBlock(title, rows));
};

const formatPreviewEntry = (
  indexLabel: string,
  label: "zh" | "en",
  content: string | null | undefined,
  highlight: boolean,
): string => {
  const markerRaw = highlight ? "(!)" : "·";
  const paddedMarkerRaw = markerRaw.padEnd(3, " ");
  const baseStyled = highlight ? styles.red("(!)") : styles.gray("·");
  const styledPadLength = paddedMarkerRaw.length - stripAnsi(baseStyled).length;
  const markerStyled =
    styledPadLength > 0
      ? `${baseStyled}${" ".repeat(styledPadLength)}`
      : baseStyled;
  const safeContent =
    content === null || content === undefined || content.length === 0
      ? styles.red("(missing)")
      : content;

  const plainIndex =
    label === "zh" ? indexLabel : " ".repeat(indexLabel.length);
  const styledIndex =
    label === "zh" ? styles.bold(indexLabel) : " ".repeat(indexLabel.length);

  const rawPrefix = `${paddedMarkerRaw} ${plainIndex} ${label}: `;
  const styledPrefix = `${markerStyled} ${styledIndex} ${styles.dim(label)}: `;
  const indentedContent = safeContent.replace(
    /\n/g,
    `\n${" ".repeat(rawPrefix.length)}`,
  );

  return `${styledPrefix}${indentedContent}`;
};

const formatSentenceCount = (
  count: number,
  relation: "more" | "fewer" | null,
) => {
  const relationText =
    relation === "more"
      ? ` ${styles.yellow("(more)")}`
      : relation === "fewer"
        ? ` ${styles.red("(fewer)")}`
        : "";
  return `${count}${relationText}`;
};

const formatMetadataRows = (entries: Array<[string, string]>): string[] => {
  const maxLabelLength = entries.reduce(
    (max, [label]) => Math.max(max, stripAnsi(label).length),
    0,
  );

  return entries.map(([label, value]) => {
    const paddedLabel = label.padEnd(maxLabelLength, " ");
    return `${styles.dim(paddedLabel)} : ${value}`;
  });
};

const generateSegments = async () => {
  const lintWarnings: Array<{
    chapter: number;
    segment: number;
    title: string;
    rows: string[];
  }> = [];

  let entries: Array<{
    id: string;
    text: string;
    audioPath: string;
    translation: string | null;
    isCodeBlock: boolean;
    sentences: Array<{
      chinese: string;
      english: string | null;
      transcription: string | null;
      durationInFrames: number;
    }>;
    durationInFrames: number;
  }> = [];

  // Load chapter metadata files
  const chapterMetadata: Record<
    string,
    Record<string, { isCodeBlock: boolean }>
  > = {};
  try {
    const metadataFiles = readdirSync(SEGMENTS_DIR).filter((file) =>
      file.endsWith(".json"),
    );
    for (const metadataFile of metadataFiles) {
      const metadataPath = join(SEGMENTS_DIR, metadataFile);
      const metadata = JSON.parse(
        readFileSync(metadataPath, "utf-8"),
      ) as Record<string, { isCodeBlock: boolean }>;
      const chapterNum = metadataFile.replace(".json", "");
      chapterMetadata[chapterNum] = metadata;
    }
  } catch (error) {
    console.warn("[segments] Failed to load chapter metadata:", error);
  }

  try {
    const files = readdirSync(SEGMENTS_DIR).filter((file) =>
      file.endsWith(".txt"),
    );

    entries = (
      await Promise.all(
        files.map(async (file) => {
          const id = file.replace(".txt", "");
          const audioFile = `audio-${id}.mp3`;
          const femaleAudioFile = `audio-${id}-f.mp3`;
          const maleAudioPath = join(AUDIOS_DIR, audioFile);
          const femaleAudioPath = join(AUDIOS_FEMALE_DIR, femaleAudioFile);
          const hasFemaleAudio = existsSync(femaleAudioPath);
          const sourceAudioPath = hasFemaleAudio
            ? femaleAudioPath
            : maleAudioPath;
          const publicAudioFile = hasFemaleAudio
            ? `female/${femaleAudioFile}`
            : audioFile;

          if (!existsSync(sourceAudioPath)) {
            debugLog(`Skipping ${file} (no matching audio).`);
            return null;
          }

          // Get chapter number from segment ID (e.g., "3-1" -> "3")
          const chapterNum = id.split("-")[0];
          const metadata = chapterMetadata[chapterNum]?.[id];
          const isCodeBlock = metadata?.isCodeBlock ?? false;

          const segmentPath = join(SEGMENTS_DIR, file);
          const rawText = readFileSync(segmentPath, "utf-8");
          const text = isCodeBlock ? rawText : rawText.trim();
          const translationPath = join(TRANSLATIONS_DIR, `${id}.txt`);
          const rawTranslation = existsSync(translationPath)
            ? readFileSync(translationPath, "utf-8")
            : null;
          const translation =
            isCodeBlock && rawTranslation
              ? rawTranslation
              : (rawTranslation?.trim() ?? null);
          const transcriptPath = join(TRANSCRIPTS_DIR, `audio-${id}.txt`);
          const rawTranscript = existsSync(transcriptPath)
            ? readFileSync(transcriptPath, "utf-8")
            : null;
          const transcript =
            isCodeBlock && rawTranscript
              ? rawTranscript
              : (rawTranscript?.trim() ?? null);

          const chineseSentences = splitChineseSentences(text, isCodeBlock);
          const englishSentences = splitEnglishSentences(
            translation,
            isCodeBlock,
          );
          const ipaSentences = splitIPATranscriptions(
            transcript,
            chineseSentences,
            isCodeBlock,
          );

          // ------------------------------------------------------------------
          // Translation sanity checks
          //
          // Emit a compiler-style warning if:
          // - There is Chinese text but the overall English translation is
          //   empty/missing.
          // - The number of English sentences differs from the number of Chinese
          //   sentences for this segment (missing or extra lines).
          // ------------------------------------------------------------------
          const hasChinese = chineseSentences.length > 0;
          const trimmedTranslation =
            translation !== null ? translation.trim() : translation;
          const englishIsEmpty =
            hasChinese &&
            (trimmedTranslation === null || trimmedTranslation.length === 0);
          const sentenceCountMismatch =
            englishSentences.length !== chineseSentences.length;

          if (englishIsEmpty || sentenceCountMismatch) {
            const relation =
              englishSentences.length > chineseSentences.length
                ? "more"
                : "fewer";

            const previews: string[] = [];
            const maxPairs = Math.max(
              chineseSentences.length,
              englishSentences.length,
            );
            for (let i = 0; i < maxPairs; i++) {
              const c = chineseSentences[i];
              const e = englishSentences[i];
              if (c === undefined && e === undefined) {
                break;
              }
              const indexLabel = `#${i.toString().padStart(2, "0")}`;
              const highlight = c === undefined || e === undefined;
              previews.push(formatPreviewEntry(indexLabel, "zh", c, highlight));
              previews.push(formatPreviewEntry(indexLabel, "en", e, highlight));
            }

            const metadataRows = formatMetadataRows([
              ["Segmented text", toRendererRelative(segmentPath)],
              [
                "Eng. Translation",
                existsSync(translationPath)
                  ? toRendererRelative(translationPath)
                  : styles.red("(missing)"),
              ],
              [
                "Chinese sentences",
                formatSentenceCount(chineseSentences.length, null),
              ],
              [
                "English sentences",
                formatSentenceCount(englishSentences.length, relation),
              ],
            ]);

            const rows = [
              ...metadataRows,
              ...(previews.length > 0
                ? [INNER_DIVIDER_TOKEN, ...previews]
                : []),
            ];

            const [chapterStr, segmentStr] = id.split("-");
            lintWarnings.push({
              chapter: Number(chapterStr),
              segment: Number(segmentStr),
              title: `⚠️  Translation mismatch in ${id}`,
              rows,
            });
          }

          if (hasFemaleAudio) {
            debugLog(`Using female voice for segment ${id}.`);
          }

          const durationInSeconds =
            await getAudioDurationInSeconds(sourceAudioPath);
          const durationInFrames =
            Math.ceil(durationInSeconds * FPS) + AUDIO_TAIL_FRAMES;

          let assignedFrames = 0;
          const totalChars = chineseSentences
            .map((sentence) => countCharsExcludingQuotes(sentence))
            .reduce((sum, count) => sum + count, 0);

          const sentences = chineseSentences.map((chSentence, index) => {
            const charCount = countCharsExcludingQuotes(chSentence);
            const isLast = index === chineseSentences.length - 1;
            const proportion =
              totalChars > 0
                ? charCount / totalChars
                : 1 / Math.max(chineseSentences.length, 1);

            let sentenceDuration = isLast
              ? durationInFrames - assignedFrames
              : Math.max(Math.round(durationInFrames * proportion), 1);

            if (!isLast) {
              assignedFrames += sentenceDuration;
            } else {
              const remaining = durationInFrames - assignedFrames;
              if (remaining > 0) {
                sentenceDuration = remaining;
                assignedFrames += remaining;
              }
            }

            const englishSentence = englishSentences[index] ?? null;
            const ipaSentence = ipaSentences[index] ?? null;

            return {
              chinese: chSentence,
              english: englishSentence,
              transcription: ipaSentence,
              durationInFrames: sentenceDuration,
            };
          });

          return {
            id,
            text,
            audioPath: `audios/${publicAudioFile}`,
            translation,
            isCodeBlock,
            sentences,
            durationInFrames,
          };
        }),
      )
    )
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null)
      .sort((a, b) => {
        const [aChapter, aSegment] = a.id.split("-").map(Number);
        const [bChapter, bSegment] = b.id.split("-").map(Number);

        if (aChapter !== bChapter) {
          return aChapter - bChapter;
        }

        return aSegment - bSegment;
      });
  } catch (error) {
    console.error("[segments] Failed to read segments:", error);
    entries = [];
  }

  lintWarnings
    .sort(
      (a, b) =>
        b.chapter - a.chapter || a.segment - b.segment,
    )
    .forEach((warning) => {
      logLintWarning(warning.title, warning.rows);
    });

  mkdirSync(GENERATED_DIR, { recursive: true });

  // Remove old per-chapter files to avoid stale data
  try {
    const generatedFiles = readdirSync(GENERATED_DIR);
    for (const file of generatedFiles) {
      if (file.startsWith("segments-") && file.endsWith(".ts")) {
        const filePath = join(GENERATED_DIR, file);
        unlinkSync(filePath);
      }
    }
  } catch (error) {
    console.warn(
      "[segments] Failed to clean generated segments directory:",
      error,
    );
  }

  const fileHeader =
    `// Auto-generated by renderer/scripts/generate-segments.ts. Do not edit manually.\n` +
    `// Regenerate this file by running the generate-segments script.\n\n`;

  // Group entries by chapter number (e.g., "3-1" -> chapter "3")
  const chapters: Record<string, typeof entries> = {};
  for (const entry of entries) {
    const chapterNum = entry.id.split("-")[0];
    if (!chapters[chapterNum]) {
      chapters[chapterNum] = [];
    }
    chapters[chapterNum].push(entry);
  }

  // Sort chapters numerically to keep file generation stable
  const chapterNumbers = Object.keys(chapters).sort(
    (a, b) => Number(a) - Number(b),
  );

  // Generate one file per chapter with that chapter's segments
  for (const chapterNum of chapterNumbers) {
    const chapterEntries = chapters[chapterNum];
    const chapterFilePath = join(GENERATED_DIR, `segments-${chapterNum}.ts`);
    const chapterFileContents =
      fileHeader +
      `export const segments = ${JSON.stringify(chapterEntries, null, 2)} as const;\n` +
      `export type Segment = typeof segments[number];\n`;

    writeFileSync(chapterFilePath, chapterFileContents);
  }

  // Generate a small index file that aggregates all chapters
  const importLines = chapterNumbers
    .map(
      (chapterNum) =>
        `import { segments as segments${chapterNum} } from "./segments-${chapterNum}";`,
    )
    .join("\n");

  const allSegmentsExpression =
    chapterNumbers.length > 0
      ? `[${chapterNumbers
          .map((chapterNum) => `...segments${chapterNum}`)
          .join(", ")}]`
      : "[]";

  const indexFileContents =
    fileHeader +
    importLines +
    (importLines ? "\n\n" : "") +
    `export const segments = ${allSegmentsExpression} as const;\n` +
    `export type Segment = (typeof segments)[number];\n`;

  writeFileSync(GENERATED_SEGMENTS_FILE, indexFileContents);
};

generateSegments()
  .then(() => {
    debugLog("Segment metadata generation complete.");
  })
  .catch((error) => {
    console.error("[segments] Segment metadata generation failed:", error);
    process.exitCode = 1;
  });
