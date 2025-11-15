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

import { APPROX_SECONDS_PER_CHARACTER } from "../constants/narration";

const rendererDir = process.env.RENDERER_DIR ?? process.cwd();
const AUDIOS_DIR = join(rendererDir, "public", "audios");
const AUDIOS_FEMALE_DIR = join(AUDIOS_DIR, "female");
const SEGMENTS_JSON_DIR = join(rendererDir, "public", "segments");
const SENTENCES_JSON_DIR = join(rendererDir, "public", "sentences");
const TRANSLATIONS_DIR = join(rendererDir, "public", "translations");
const TRANSCRIPTIONS_DIR = join(rendererDir, "public", "transcripts");
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

// Counts characters used to proportionally allocate audio duration across
// Chinese sentences. This is about timing (how long a line should be on
// screen), not IPA alignment, so we ignore punctuation and whitespace that
// is not actually spoken.
const countCharsExcludingQuotes = (text: string): number => {
  return text.replace(/[「」『』`\n\t 　]/g, "").length;
};

const estimateDurationFromCharCount = (charCount: number): number => {
  if (!Number.isFinite(charCount) || charCount <= 0) {
    return DEFAULT_AUDIO_DURATION_SECONDS;
  }
  return charCount * APPROX_SECONDS_PER_CHARACTER;
};

type SentenceSegment = {
  id: string;
  chapterId: string;
  segmentIndex: number;
  sentenceIds: string[];
  isCodeBlock: boolean;
};

type ChapterSegmentsFile = {
  chapterId?: string;
  chapterNumber?: number;
  segments?: SentenceSegment[];
};

type SentenceJsonEntry = {
  id: string;
  source: string;
  isCode: boolean;
};

type SentencesFile = {
  sentences: SentenceJsonEntry[];
};

type TranslationEntry = {
  translation?: string | null;
};

type TranscriptionEntry = {
  ipa?: string | null;
};

type ChapterResources = {
  sentences: Map<string, SentenceJsonEntry>;
  translations: Map<string, string | null>;
  transcriptions: Map<string, string | null>;
};

const chapterResourcesCache = new Map<string, ChapterResources | null>();

const readJsonFile = <T>(filePath: string): T | null => {
  if (!existsSync(filePath)) {
    return null;
  }
  try {
    const raw = readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch (error) {
    console.warn(`[segments] Failed to parse ${filePath}:`, error);
    return null;
  }
};

const parseChapterNumber = (fileName: string): number => {
  const match = fileName.match(/^c(\d+)/i);
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
};

const loadSentenceSegmentsIndex = (): SentenceSegment[] => {
  if (!existsSync(SEGMENTS_JSON_DIR)) {
    throw new Error(
      `[segments] Segments directory not found: ${SEGMENTS_JSON_DIR}`,
    );
  }

  const files = readdirSync(SEGMENTS_JSON_DIR)
    .filter((file) => file.endsWith(".segments.json"))
    .sort((a, b) => parseChapterNumber(a) - parseChapterNumber(b));

  if (files.length === 0) {
    throw new Error(
      `[segments] No *.segments.json files found in ${SEGMENTS_JSON_DIR}`,
    );
  }

  const records: SentenceSegment[] = [];
  for (const file of files) {
    const filePath = join(SEGMENTS_JSON_DIR, file);
    const parsed = readJsonFile<ChapterSegmentsFile>(filePath);
    if (!parsed || !Array.isArray(parsed.segments)) {
      console.warn(
        `[segments] Skipping ${toRendererRelative(filePath)} (missing segments array)`,
      );
      continue;
    }

    const fallbackChapterId =
      parsed.chapterId ?? file.replace(/\.segments\.json$/, "");

    parsed.segments.forEach((segment, index) => {
      if (!segment || typeof segment !== "object") {
        return;
      }
      const sentenceIds = Array.isArray(segment.sentenceIds)
        ? segment.sentenceIds.filter((value): value is string => {
            return typeof value === "string";
          })
        : [];

      if (!segment.id) {
        console.warn(
          `[segments] Segment entry ${index} in ${toRendererRelative(filePath)} is missing an id; skipping.`,
        );
        return;
      }

      const segmentIndex = Number(segment.segmentIndex);

      records.push({
        id: segment.id,
        chapterId: segment.chapterId ?? fallbackChapterId,
        segmentIndex: Number.isFinite(segmentIndex) ? segmentIndex : index + 1,
        sentenceIds,
        isCodeBlock: Boolean(segment.isCodeBlock),
      });
    });
  }

  if (records.length === 0) {
    throw new Error(
      "[segments] No valid segments loaded from chapter segment JSON files.",
    );
  }

  return records;
};

const cleanEnglishLine = (input: string | null | undefined): string | null => {
  if (!input) {
    return null;
  }
  const trimmed = input.trim();
  return trimmed.length > 0 ? trimmed : null;
};

const cleanTranscription = (
  input: string | null | undefined,
): string | null => {
  if (!input) {
    return null;
  }
  const trimmed = input.trim();
  const withoutTrailingDots = trimmed.replace(/(?:\s*\.)+$/g, "").trim();
  return withoutTrailingDots.length > 0 ? withoutTrailingDots : null;
};

const formatChineseSentence = (
  source: string | undefined,
  preserveWhitespace: boolean,
): string => {
  if (!source) {
    return "";
  }
  return preserveWhitespace ? source : source.trim();
};

const buildTranslationBlock = (lines: Array<string | null>): string | null => {
  if (lines.length === 0) {
    return null;
  }
  const joined = lines
    .map((line) => line ?? "")
    .join("\n")
    .trim();
  return joined.length > 0 ? joined : null;
};

const resolveTranscriptionPath = (chapterId: string): string | null => {
  const candidates = [
    join(TRANSCRIPTIONS_DIR, `${chapterId}.transcriptions.json`),
    join(TRANSCRIPTIONS_DIR, `${chapterId}.transcripts.json`),
  ];

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  return null;
};

const loadChapterResources = (chapterId: string): ChapterResources | null => {
  const cached = chapterResourcesCache.get(chapterId);
  if (cached !== undefined) {
    return cached;
  }

  const sentencesPath = join(SENTENCES_JSON_DIR, `${chapterId}.sentences.json`);
  const translationsPath = join(
    TRANSLATIONS_DIR,
    `${chapterId}.translations.json`,
  );
  const transcriptionsPath = resolveTranscriptionPath(chapterId);

  const sentencesJson = readJsonFile<SentencesFile>(sentencesPath);
  if (!sentencesJson || !Array.isArray(sentencesJson.sentences)) {
    console.warn(
      `[segments] Missing or invalid sentences for ${chapterId} at ${toRendererRelative(sentencesPath)}`,
    );
    chapterResourcesCache.set(chapterId, null);
    return null;
  }

  const sentences = new Map<string, SentenceJsonEntry>();
  sentencesJson.sentences.forEach((entry) => {
    if (entry?.id) {
      sentences.set(entry.id, entry);
    }
  });

  const translationsRaw =
    readJsonFile<Record<string, TranslationEntry>>(translationsPath);
  if (!translationsRaw) {
    console.warn(
      `[segments] Missing translations for ${chapterId} at ${toRendererRelative(translationsPath)}`,
    );
  }
  const translations = new Map<string, string | null>();
  if (translationsRaw) {
    Object.entries(translationsRaw).forEach(([id, entry]) => {
      translations.set(id, cleanEnglishLine(entry?.translation ?? null));
    });
  }

  const transcriptions = new Map<string, string | null>();
  if (transcriptionsPath) {
    const transcriptionRaw =
      readJsonFile<Record<string, TranscriptionEntry>>(transcriptionsPath);
    if (transcriptionRaw) {
      Object.entries(transcriptionRaw).forEach(([id, entry]) => {
        transcriptions.set(id, cleanTranscription(entry?.ipa ?? null));
      });
    } else {
      console.warn(
        `[segments] Failed to parse transcriptions for ${chapterId} at ${toRendererRelative(transcriptionsPath)}`,
      );
    }
  } else {
    console.warn(
      `[segments] No transcriptions JSON found for ${chapterId} in ${toRendererRelative(TRANSCRIPTIONS_DIR)}`,
    );
  }

  const resources: ChapterResources = {
    sentences,
    translations,
    transcriptions,
  };
  chapterResourcesCache.set(chapterId, resources);
  return resources;
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

const generateSegments = async () => {
  const lintWarnings: Array<{
    chapter: number;
    segment: number;
    title: string;
    rows: string[];
  }> = [];

  const missingAudioByChapter = new Map<number, Set<string>>();
  const recordMissingAudio = (chapter: number, ...paths: string[]) => {
    const target = missingAudioByChapter.get(chapter) ?? new Set<string>();
    paths.forEach((path) => {
      if (path) {
        target.add(`(!) ${toRendererRelative(path)}`);
      }
    });
    missingAudioByChapter.set(chapter, target);
  };

  const sentenceSegments = loadSentenceSegmentsIndex();
  const segmentsToProcess: readonly SentenceSegment[] = [...sentenceSegments];

  const entries = (
    await Promise.all(
      segmentsToProcess.map(async (segmentDef) => {
        const { id, chapterId, sentenceIds, isCodeBlock, segmentIndex } =
          segmentDef;
        const audioFile = `audio-${id}.mp3`;
        const femaleAudioFile = `audio-${id}-f.mp3`;
        const maleAudioPath = join(AUDIOS_DIR, audioFile);
        const femaleAudioPath = join(AUDIOS_FEMALE_DIR, femaleAudioFile);
        const hasMaleAudio = existsSync(maleAudioPath);
        const hasFemaleAudio = existsSync(femaleAudioPath);
        const sourceAudioPath = hasFemaleAudio
          ? femaleAudioPath
          : hasMaleAudio
            ? maleAudioPath
            : null;
        const publicAudioFile = hasFemaleAudio
          ? `female/${femaleAudioFile}`
          : hasMaleAudio
            ? audioFile
            : null;

        if (!sourceAudioPath) {
          const chapterNum = Number(id.split("-")[0]) || 0;
          recordMissingAudio(chapterNum, maleAudioPath, femaleAudioPath);
        }

        const resources = loadChapterResources(chapterId);
        if (!resources) {
          lintWarnings.push({
            chapter: Number(id.split("-")[0]) || 0,
            segment: segmentIndex,
            title: `⚠️  Missing chapter resources for ${id}`,
            rows: [
              `Sentences: ${toRendererRelative(
                join(SENTENCES_JSON_DIR, `${chapterId}.sentences.json`),
              )}`,
              `Translations: ${toRendererRelative(
                join(TRANSLATIONS_DIR, `${chapterId}.translations.json`),
              )}`,
              `Transcriptions dir: ${toRendererRelative(TRANSCRIPTIONS_DIR)}`,
            ],
          });
          return null;
        }

        if (!sentenceIds || sentenceIds.length === 0) {
          lintWarnings.push({
            chapter: Number(id.split("-")[0]) || 0,
            segment: segmentIndex,
            title: `⚠️  No sentence mapping for ${id}`,
            rows: [
              `Chapter ${chapterId} has no sentenceIds entry in ${chapterId}.segments.json`,
            ],
          });
          return null;
        }

        const { sentences, translations, transcriptions } = resources;
        const missingChinese: string[] = [];
        const missingTranslations: string[] = [];
        const missingTranscriptions: string[] = [];

        const chineseTexts: string[] = [];
        const englishLines: Array<string | null> = [];
        const transcriptionLines: Array<string | null> = [];

        for (const sentenceId of sentenceIds) {
          const sentenceEntry = sentences.get(sentenceId);
          if (!sentenceEntry) {
            missingChinese.push(sentenceId);
          }
          const preserveWhitespace =
            isCodeBlock || Boolean(sentenceEntry?.isCode);
          const chinese = formatChineseSentence(
            sentenceEntry?.source,
            preserveWhitespace,
          );
          chineseTexts.push(chinese);

          const hasTranslation = translations.has(sentenceId);
          const english = translations.get(sentenceId) ?? null;
          if (!hasTranslation || english === null) {
            missingTranslations.push(sentenceId);
          }
          englishLines.push(english);

          const hasTranscription = transcriptions.has(sentenceId);
          const ipa = transcriptions.get(sentenceId) ?? null;
          if (!hasTranscription || ipa === null) {
            missingTranscriptions.push(sentenceId);
          }
          transcriptionLines.push(ipa);
        }

        const perSentenceCharCounts = chineseTexts.map((sentence) => {
          return countCharsExcludingQuotes(sentence);
        });
        const totalChars = perSentenceCharCounts.reduce(
          (sum, count) => sum + count,
          0,
        );

        const text = isCodeBlock
          ? chineseTexts.join("")
          : chineseTexts.join("").trim();
        const translationBlock = buildTranslationBlock(englishLines);

        if (hasFemaleAudio) {
          debugLog(`Using female voice for segment ${id}.`);
        }

        const durationInSeconds = sourceAudioPath
          ? await getAudioDurationInSeconds(sourceAudioPath)
          : estimateDurationFromCharCount(totalChars);
        const durationInFrames =
          Math.ceil(durationInSeconds * FPS) + AUDIO_TAIL_FRAMES;

        let assignedFrames = 0;
        const sentencesForOutput = chineseTexts.map((chSentence, index) => {
          const charCount = perSentenceCharCounts[index];
          const isLast = index === chineseTexts.length - 1;
          const proportion =
            totalChars > 0
              ? charCount / totalChars
              : 1 / Math.max(chineseTexts.length, 1);

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

          return {
            chinese: chSentence,
            english: englishLines[index],
            transcription: transcriptionLines[index],
            durationInFrames: sentenceDuration,
          };
        });

        const [chapterStr] = id.split("-");
        const chapterNum = Number(chapterStr) || 0;
        const warnRows = (label: string, ids: string[]): void => {
          if (ids.length === 0) {
            return;
          }
          lintWarnings.push({
            chapter: chapterNum,
            segment: segmentIndex,
            title: `⚠️  Missing ${label} in ${id}`,
            rows: ids.map((missingId) => `  - ${missingId}`),
          });
        };

        warnRows("Chinese sentences", missingChinese);
        warnRows("translations", missingTranslations);
        warnRows("transcriptions", missingTranscriptions);

        return {
          id,
          text,
          audioPath: publicAudioFile ? `audios/${publicAudioFile}` : null,
          translation: translationBlock,
          isCodeBlock,
          sentences: sentencesForOutput,
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

  for (const [chapter, paths] of [...missingAudioByChapter.entries()].sort(
    (a, b) => a[0] - b[0],
  )) {
    lintWarnings.push({
      chapter,
      segment: 0,
      title: `⚠️  Missing narration audio for chapter ${chapter}`,
      rows: [...paths],
    });
  }

  lintWarnings
    .sort((a, b) => b.chapter - a.chapter || a.segment - b.segment)
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
