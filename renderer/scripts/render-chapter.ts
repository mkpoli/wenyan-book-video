const chapterArg = process.argv[2];

if (!chapterArg) {
  console.error("Usage: bun run render:chapter -- <chapterNumber>");
  process.exit(1);
}

const chapter = Number(chapterArg);

if (!Number.isInteger(chapter) || chapter < 1 || chapter > 13) {
  console.error("Chapter number must be an integer between 1 and 13.");
  process.exit(1);
}

const composition = `Chapter${chapter}`;
const output = `out/chapter${chapter}.mp4`;
const props = JSON.stringify({ chapterNumber: chapter });

async function main() {
  const proc = Bun.spawn(
    [
      "./node_modules/.bin/remotion",
      "render",
      composition,
      "--props",
      props,
      output,
    ],
    {
      stdout: "inherit",
      stderr: "inherit",
    },
  );

  const exitCode = await proc.exited;

  if (exitCode !== 0) {
    console.error(
      `Rendering chapter ${chapter} failed with exit code ${exitCode}.`,
    );
    process.exit(exitCode);
  }

  console.log(`Finished rendering chapter ${chapter} to ${output}.`);
}

void main().catch((err) => {
  console.error(err);
  process.exit(1);
});

export {};
