# AGENTS.md

## Purpose
- Coordinate work on the Wenyan Book Video monorepo so that automation agents share the same expectations and tools.

## Key Practices
- Always use the `bun` command (e.g., `bun install`, `bun run …`) instead of `npm` or `npx` for any JavaScript/TypeScript task.
- In `processor/`, the Python environment are all managed by `uv`. Use `uv run` to run Python scripts. When importing, the whole processor is a package itself, so if you are in it, just import relatively, i.e use `from utils.cli_style import print_warning` instead of `from processor.utils.cli_style import print_warning`.
- Keep the `book/` directory in sync via git submodules; only modify it when intentionally updating the upstream text and commit the submodule pointer, not the contents.
- Prefer incremental changes plus small, verifiable commits; document any generated assets or large outputs rather than committing binaries unless explicitly required.

## Workflow Highlights
1. **Setup** – After cloning, execute `git submodule update --init --recursive`, then `bun install` in the repo root so all workspaces share dependencies.
2. **Processing** – Use the Python tools in `processor/` (see `processor/README.md`) to create JSON, audio, and transcript artifacts that populate `renderer/public/**`.
3. **Segment Generation** – From `renderer/`, run `bun run scripts/generate-segments.ts` to materialize `renderer/src/generated/segments-*.ts` files once new processor output is ready.
4. **Rendering** – Still inside `renderer/`, run `bun run remotion render` to produce final videos; make sure the previously generated assets exist before rendering.

## Additional Notes
- Large media folders (`audios/`, `segments/`, `timings/`, etc.) can be regenerated; avoid editing them manually unless a pipeline script explicitly requires it.
- Keep README files current whenever you adjust workflows so future agents inherit accurate instructions.
