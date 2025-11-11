// See all configuration options: https://remotion.dev/docs/config
// Each option also is available as a CLI flag: https://remotion.dev/docs/cli

// Note: When using the Node.JS APIs, the config file doesn't apply. Instead, pass options directly to the APIs

import { Config } from "@remotion/cli/config";
import { enableTailwind } from "@remotion/tailwind-v4";
import { spawnSync } from "child_process";
import { existsSync } from "fs";
import { join } from "path";

const ensureSegmentsGenerated = () => {
  const rendererDir = process.cwd();
  const scriptPath = join(rendererDir, "scripts", "generate-segments.ts");

  if (!existsSync(scriptPath)) {
    throw new Error(
      `Expected segments generator at ${scriptPath}. Did you delete or move it?`,
    );
  }

  const result = spawnSync("bun", ["run", "scripts/generate-segments.ts"], {
    stdio: "inherit",
    cwd: rendererDir,
    env: {
      ...process.env,
      PROJECT_ROOT: join(rendererDir, ".."),
      RENDERER_DIR: rendererDir,
    },
  });

  if (result.error) {
    if ((result.error as NodeJS.ErrnoException).code === "ENOENT") {
      throw new Error(
        "Bun is required to generate segment metadata. Please install Bun and try again.",
      );
    }

    throw result.error;
  }

  if (result.status !== 0) {
    throw new Error(
      `Segment metadata generation failed with exit code ${result.status}.`,
    );
  }
};

ensureSegmentsGenerated();

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.overrideWebpackConfig((config) => enableTailwind(config));
