import fs from 'node:fs';
import { convertCinixToTUPA, convertCinixTo音韻地位, getDefinitionFromSinograph } from 'transcription-utils';

interface LookupEntry {
  char: string;
  readings: string[];
}

interface LookupPayload {
  entries: LookupEntry[];
}

interface MeaningResult {
  transcription: string;
  meaning: string;
  hasDefinition: boolean;
}

type MeaningMap = Record<string, MeaningResult[]>;

function ensureArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === 'string');
  }
  return [];
}

function readPayload(): LookupPayload | null {
  const rawInput = fs.readFileSync(0, 'utf8').trim();
  if (!rawInput) {
    return null;
  }
  try {
    const parsed = JSON.parse(rawInput);
    if (parsed && typeof parsed === 'object' && Array.isArray(parsed.entries)) {
      return {
        entries: parsed.entries.map((entry: unknown) => {
          if (!entry || typeof entry !== 'object') {
            return { char: '', readings: [] };
          }
          const { char, readings } = entry as { char?: unknown; readings?: unknown };
          return {
            char: typeof char === 'string' ? char : '',
            readings: ensureArray(readings),
          };
        }),
      };
    }
  } catch (error) {
    console.error('Failed to parse lookup payload:', error);
  }
  return null;
}

function buildDefinitionMap(char: string) {
  const definitions = getDefinitionFromSinograph(char);
  const map = new Map<string, string[]>();

  for (const item of definitions) {
    const description = item.pronunciation?.描述;
    const definition = item.definition ?? '';
    if (!description) {
      continue;
    }
    const current = map.get(description);
    if (current) {
      current.push(definition);
    } else {
      map.set(description, [definition]);
    }
  }

  return map;
}

function formatDefinition(description: string, definitions: string[]): string {
  if (definitions.length === 0) {
    return `【${description}】`;
  }
  return definitions
    .map((definition) => (definition ? `【${description}】${definition}` : `【${description}】`))
    .join('；');
}

function mergeIntoResult(result: MeaningMap, char: string, readings: string[], definitionMap: Map<string, string[]>) {
  const leftover = new Map(definitionMap);
  const charResults: Array<MeaningResult & { prefix: string }> = [];

  for (const reading of readings) {
    const trimmed = reading.trim();
    let meaning = '';
    let prefix = '';

    if (trimmed.length > 0) {
      try {
        const tupa = convertCinixToTUPA(trimmed);
        prefix = `${tupa} [${trimmed}]`;
      } catch (error) {
        console.warn(`Failed to convert cinix to TUPA for "${trimmed}":`, error);
        prefix = `[${trimmed}]`;
      }

      try {
        const 音韻地位 = convertCinixTo音韻地位(trimmed);
        const description = 音韻地位.描述;
        const matched = leftover.get(description);

        if (matched && matched.length > 0) {
          meaning = formatDefinition(description, matched);
          leftover.delete(description);
        }
      } catch (error) {
        console.warn(`Failed to convert cinix to 音韻地位 for "${trimmed}":`, error);
      }
    } else if (trimmed.length === 0) {
      prefix = '';
    }

    const hasDefinition = meaning.trim().length > 0;

    charResults.push({
      transcription: trimmed,
      meaning,
      hasDefinition,
      prefix,
    });
  }

  const fallbackCandidates = [...leftover.entries()].map(([description, defs]) => formatDefinition(description, defs));

  if (fallbackCandidates.length > 0) {
    const fallback = fallbackCandidates.join(' ｜ ');
    for (const item of charResults) {
      if (!item.meaning) {
        item.meaning = fallback;
        item.hasDefinition = fallback.trim().length > 0;
      }
    }
  }

  if (charResults.length === 0) {
    result[char] = [
      {
        transcription: '',
        meaning: fallbackCandidates.join(' ｜ ') || 'No local definition available for this character.',
        hasDefinition: fallbackCandidates.length > 0,
      },
    ];
  } else {
    result[char] = charResults.map(({ transcription, meaning, hasDefinition, prefix }) => {
      const parts = [prefix, meaning].filter((part) => part && part.trim().length > 0);
      return {
        transcription,
        meaning: parts.join(' '),
        hasDefinition: hasDefinition || parts.length > 1,
      };
    });
  }
}

function main() {
  const payload = readPayload();
  const result: MeaningMap = {};

  if (!payload) {
    process.stdout.write('{}');
    return;
  }

  for (const { char, readings } of payload.entries) {
    if (!char) {
      continue;
    }
    const definitionMap = buildDefinitionMap(char);
    mergeIntoResult(result, char, readings, definitionMap);
  }

  process.stdout.write(JSON.stringify(result));
}

main();
