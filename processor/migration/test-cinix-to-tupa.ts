import { readdirSync, readFileSync } from 'fs';
import { join } from 'path';
import { convertCinixToTUPA } from '../../transcription-utils';

const ROOT = process.cwd();
const TRANSCRIPTS_DIR = join(ROOT, 'renderer', 'public', 'transcripts');

type SentenceEntry = {
  source?: string;
  ipa?: string;
  tupa?: string;
};

const normalize = (value: string | undefined | null): string => (value ?? '').trim();

const main = () => {
  const files = readdirSync(TRANSCRIPTS_DIR).filter((file) => file.match(/^c\d+\.sentences\.json$/));

  if (files.length === 0) {
    console.log('[test-cinix-to-tupa] No c*.sentences.json files found in', TRANSCRIPTS_DIR);
    process.exitCode = 1;
    return;
  }

  let totalChecked = 0;
  let totalMismatches = 0;
  const mismatchSamples: string[] = [];

  for (const file of files.sort()) {
    const fullPath = join(TRANSCRIPTS_DIR, file);
    const json = JSON.parse(readFileSync(fullPath, 'utf-8')) as Record<string, SentenceEntry>;

    for (const [sentId, entry] of Object.entries(json)) {
      const ipa = normalize(entry.ipa);
      const tupaPython = normalize(entry.tupa);
      if (!ipa) continue;

      const tupaJs = normalize(convertCinixToTUPA(ipa));
      totalChecked += 1;

      if (tupaJs !== tupaPython) {
        totalMismatches += 1;
        if (mismatchSamples.length < 20) {
          mismatchSamples.push(
            [
              `File: ${file}`,
              `Sentence: ${sentId}`,
              `IPA:      ${ipa}`,
              `Python:   ${tupaPython}`,
              `JS/TS:    ${tupaJs}`,
            ].join('\n')
          );
        }
      }
    }
  }

  console.log(`[test-cinix-to-tupa] Checked ${totalChecked} sentence(s),` + ` mismatches: ${totalMismatches}`);

  if (mismatchSamples.length > 0) {
    console.log('\nFirst mismatches (Python vs JS/TS convertCinixToTUPA):\n');
    console.log(mismatchSamples.join('\n\n---\n\n'));
  } else {
    console.log('[test-cinix-to-tupa] All TUPA conversions match.');
  }
};

main();
