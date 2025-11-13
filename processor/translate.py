import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    import time
    import traceback
    from pathlib import Path
    from openai import OpenAI
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()
    return OpenAI, Path, mo, os, time, traceback


@app.cell
def _(OpenAI, os):
    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set. Please set it in your .env file or environment."
        )

    client = OpenAI(api_key=api_key)
    MODEL_NAME = "gpt-5-mini"  # Using GPT-5 as requested
    API_DELAY_SECONDS = 1  # Small delay to avoid rate limits
    return API_DELAY_SECONDS, MODEL_NAME, client


@app.cell
def _():
    # Translation prompt template
    TRANSLATION_PROMPT = """You are to translate Classical Chinese prose (especially technical or literary works such as guides for the Wenyan programming language) into refined, natural English without omitting classical nuance.

    Follow these formatting and stylistic rules carefully.

    ## Translation Rules

    ### Preserve Original Format
    - Each 。 (full stop) in the original Chinese marks a new line in the translation.
    - Keep the line structure exactly; DO NOT merge sentences into paragraphs.
    - Retain all original quotation marks (「」『』) and render them faithfully using English typographical quotes (“”).
    - Preserve punctuation rhythm and rhetorical pauses as line breaks.

    ### Maintain Classical Tone
    - Use dignified, reflective, and occasionally poetic phrasing suitable for a didactic text.
    - Avoid modern or casual diction.
    - Strive for clarity while maintaining the philosophical rhythm and rhetorical symmetry of Classical Chinese.

    ### No Omission or Summarization
    - Every clause and metaphor must appear in the translation, even if slightly paraphrased for clarity.
    - Preserve original meaning and sentence order exactly.

    ### English Formatting
    - Each sentence begins on a new line.
    - Output plain text only (no Markdown, no formatting symbols).
    - Keep all nested quotations and rhetorical questions intact.
    - Use typographical punctuation (— … “” ‘ ’) to evoke a classical style.

    ## Glossary

    - “爻” should be translated as “Yáo (booleans)”.
    - “計開” means “Table of Contents”, is used as a marker to start a list of contents, can be translated as “Let’s unfold our explanation.” or "As follows," or "Let's begin." by context.

    ## Examples

    ### Example 1
    Input:
    易曰。變化者。進退之象也。今編程者。罔不以變數為本。變數者何。一名命一物也。

    Output:
    The Book of Changes says,
    “Transformation —
    is the image of advance and retreat.”

    Now, in programming,
    nothing is without variables as its foundation.

    “What is a variable?”
    “It is a name assigned to a thing.”

    ### Example 2
    Input:
    編程者何。所以役機器也。機器者何。所以代人力也。然機器之力也廣。其算也速。唯智不逮也。故有智者慎謀遠慮。下筆千言。如軍令然。如藥方然。謂之程式。機器既明之。乃能為人所使。或演星文。或析事理。

    Output:
    What is programming? That by which one commands machines.
    What is a machine? That by which human labor is replaced.
    Yet the power of machines is vast,
    their calculations swift,
    but their wisdom does not reach that of man.

    Therefore, the wise plan with care and foresight.
    They set down a thousand words,
    as if issuing military orders,
    as if prescribing medicine —
    this is called a program.

    Once the machine comprehends it,
    it can then be made to serve mankind —
    to chart the movements of the stars,
    or to analyze the patterns of reason.

    ## Your Turn
    Now translate the following Classical Chinese text:

    {text}

    With the following context:

    Before:
    {before_context}

    After:
    {after_context}
    """
    return (TRANSLATION_PROMPT,)


@app.cell
def _(Path):
    segments_dir = Path("../renderer/public/segments").resolve()
    translations_dir = Path("../renderer/public/translations").resolve()

    # Ensure translations directory exists
    translations_dir.mkdir(exist_ok=True)

    # Debug: print resolved paths
    print(f"Segments directory: {segments_dir}")
    print(f"Translations directory: {translations_dir}")
    print(f"Translations directory exists: {translations_dir.exists()}")
    return segments_dir, translations_dir


@app.cell
def _(segments_dir, translations_dir):
    # Maximum number of files to process per run (safety limit)
    MAX_FILES_PER_RUN = 1

    # Find all segment files
    # Sort naturally by extracting chapter and segment numbers
    def sort_key(path):
        # Extract numbers from filename like "1-2.txt" -> (1, 2)
        name = path.stem  # "1-2"
        parts = name.split("-")  # ["1", "2"]
        return (int(parts[0]), int(parts[1]))  # (chapter, segment)

    all_segment_files = sorted(segments_dir.glob("*.txt"), key=sort_key)

    # Filter to only files that don't have translations yet
    segment_files_to_process = []
    for segment_file in all_segment_files:
        translation_filename = f"{segment_file.stem}.txt"
        translation_path = translations_dir / translation_filename
        if not translation_path.exists():
            segment_files_to_process.append(segment_file)

    # Limit to MAX_FILES_PER_RUN
    segment_files = segment_files_to_process[:MAX_FILES_PER_RUN]

    print(f"Found {len(all_segment_files)} total segment files")
    print(f"Found {len(segment_files_to_process)} files without translations")
    print(f"Processing {len(segment_files)} files (limit: {MAX_FILES_PER_RUN} per run)")
    if segment_files:
        print(f"Files to process (in order): {[f.name for f in segment_files]}")
    return all_segment_files, segment_files


@app.cell
def _(
    API_DELAY_SECONDS,
    MODEL_NAME,
    TRANSLATION_PROMPT,
    all_segment_files,
    client,
    mo,
    segments_dir,
    time,
    traceback,
    translations_dir,
):
    def get_context(seg_file, all_segment_files, segments_dir, translations_dir):
        """Get context from previous and next segment files."""
        # Find current segment index
        current_idx = None
        for idx, f in enumerate(all_segment_files):
            if f.stem == seg_file.stem:
                current_idx = idx
                break

        before_context = ""
        after_context = ""

        # Get previous segment context
        if current_idx is not None and current_idx > 0:
            prev_file = all_segment_files[current_idx - 1]
            prev_trans_path = translations_dir / f"{prev_file.stem}.txt"

            if prev_trans_path.exists():
                # Use translation if available
                with open(prev_trans_path, "r", encoding="utf-8") as f:
                    before_context = f.read().strip()
                print(f"  📖 Context (before): Using translation from {prev_file.name}")
                print(
                    f"     Preview: {before_context[:80]}..."
                    if len(before_context) > 80
                    else f"     Content: {before_context}"
                )
            else:
                # Fall back to Chinese text
                with open(prev_file, "r", encoding="utf-8") as f:
                    before_context = f.read().strip()
                print(
                    f"  📖 Context (before): Using Chinese text from {prev_file.name}"
                )
                print(
                    f"     Preview: {before_context[:80]}..."
                    if len(before_context) > 80
                    else f"     Content: {before_context}"
                )
        else:
            print("  📖 Context (before): No previous segment (first segment)")

        # Get next segment context
        if current_idx is not None and current_idx < len(all_segment_files) - 1:
            next_file = all_segment_files[current_idx + 1]
            next_trans_path = translations_dir / f"{next_file.stem}.txt"

            if next_trans_path.exists():
                # Use translation if available
                with open(next_trans_path, "r", encoding="utf-8") as f:
                    after_context = f.read().strip()
                print(f"  📖 Context (after): Using translation from {next_file.name}")
                print(
                    f"     Preview: {after_context[:80]}..."
                    if len(after_context) > 80
                    else f"     Content: {after_context}"
                )
            else:
                # Fall back to Chinese text
                with open(next_file, "r", encoding="utf-8") as f:
                    after_context = f.read().strip()
                print(f"  📖 Context (after): Using Chinese text from {next_file.name}")
                print(
                    f"     Preview: {after_context[:80]}..."
                    if len(after_context) > 80
                    else f"     Content: {after_context}"
                )
        else:
            print("  📖 Context (after): No next segment (last segment)")

        return before_context, after_context

    def process_segments(segment_files):
        """Process segment files and generate translations."""
        if not segment_files:
            print("No files to process. All segments already have translations.")
            return

        for i, seg_file in enumerate(
            mo.status.progress_bar(
                segment_files,
                title="Translating segments",
                subtitle=f"Processing {len(segment_files)} files",
                show_rate=True,
                show_eta=True,
            ),
            1,
        ):
            trans_filename = f"{seg_file.stem}.txt"
            trans_path = translations_dir / trans_filename

            # Skip if translation already exists (safety check)
            if trans_path.exists():
                print(f"⏭ Skipping {seg_file.name}: translation already exists")
                continue

            # Read segment text
            with open(seg_file, "r", encoding="utf-8") as f:
                chinese_text = f.read().strip()

            if not chinese_text:
                print(f"⚠ Skipping {seg_file.name}: empty file")
                continue

            print(f"\n{'='*70}")
            print(f"[{i}/{len(segment_files)}] Translating {seg_file.name}...")
            print(f"{'='*70}")
            print(f"  📝 Chinese text ({len(chinese_text)} chars):")
            print(
                f"     {chinese_text[:100]}..."
                if len(chinese_text) > 100
                else f"     {chinese_text}"
            )

            # Get context from previous and next segments
            before_context, after_context = get_context(
                seg_file, all_segment_files, segments_dir, translations_dir
            )

            # Prepare prompt
            before_ctx_display = (
                before_context if before_context else "(This is the first segment.)"
            )
            after_ctx_display = (
                after_context if after_context else "(This is the last segment.)"
            )

            prompt = TRANSLATION_PROMPT.format(
                text=chinese_text,
                before_context=before_ctx_display,
                after_context=after_ctx_display,
            )

            print("  📊 Prompt statistics:")
            print(f"     - Chinese text: {len(chinese_text)} chars")
            print(f"     - Before context: {len(before_ctx_display)} chars")
            print(f"     - After context: {len(after_ctx_display)} chars")
            print(f"     - Total prompt: {len(prompt)} chars")
            print(f"  🤖 Calling API ({MODEL_NAME})...")

            try:
                # Call OpenAI API
                api_start_time = time.time()
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert translator specializing in Classical Chinese to English translation, particularly for technical and literary works.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                api_duration = time.time() - api_start_time

                # Extract translation
                translation = response.choices[0].message.content.strip()

                # Get token usage if available
                usage_info = ""
                if hasattr(response, "usage"):
                    usage = response.usage
                    usage_info = f" (tokens: {usage.total_tokens} total, {usage.prompt_tokens} prompt, {usage.completion_tokens} completion)"

                print(f"  ✅ API response received in {api_duration:.2f}s{usage_info}")
                print(f"  📄 Translation ({len(translation)} chars):")
                print(
                    f"     {translation[:150]}..."
                    if len(translation) > 150
                    else f"     {translation}"
                )

                # Save translation
                with open(trans_path, "w", encoding="utf-8") as f:
                    f.write(translation)

                print(f"  💾 Saved translation to: {trans_filename}")
                print(
                    f"     File size: {len(translation)} chars, {len(translation.splitlines())} lines"
                )

                # Wait before next API call (except for the last one)
                if i < len(segment_files):
                    print(f"  ⏳ Waiting {API_DELAY_SECONDS}s before next request...")
                    time.sleep(API_DELAY_SECONDS)

            except Exception as e:
                print(f"  ❌ Error translating {seg_file.name}: {e}")
                print("  📋 Error details:")
                traceback.print_exc()
                # Still wait to avoid rapid retries
                if i < len(segment_files):
                    print(f"  ⏳ Waiting {API_DELAY_SECONDS}s before next request...")
                    time.sleep(API_DELAY_SECONDS)

        print(f"\n{'='*70}")
        print(f"✅ Completed processing {len(segment_files)} file(s)")
        print(f"{'='*70}")
        print("💡 Tip: Run again to process more segments if any remain.")

    return (process_segments,)


@app.cell
def _(process_segments, segment_files):
    # Process each segment (already limited to MAX_FILES_PER_RUN)
    process_segments(segment_files)
    return


if __name__ == "__main__":
    app.run()
