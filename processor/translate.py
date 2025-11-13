import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    import time
    from pathlib import Path
    from openai import OpenAI
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    return OpenAI, Path, load_dotenv, mo, os, time


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

    return API_DELAY_SECONDS, MODEL_NAME, api_key, client


@app.cell
def _():
    # Translation prompt template
    TRANSLATION_PROMPT = """You are to translate Classical Chinese prose (especially technical or literary works such as guides for the Wenyan programming language) into refined, natural English without omitting classical nuance.

Follow these formatting and stylistic rules carefully:

Translation Rules

Preserve Line Structure:

Each 。 (full stop) in the original Chinese marks a new line in the translation.

Do not merge sentences into paragraphs.

Keep Quotation Marks:

Retain all original quotation marks (「」「」 or "") and render them faithfully in English using standard double quotes " ".

Maintain Classical Tone:

Use dignified, reflective phrasing suitable for a didactic text.

Avoid overly modern or casual diction.

Strive for clarity while retaining the philosophical rhythm and rhetorical symmetry of Classical Chinese.

No Omission or Summarization:

Every clause and metaphor must be represented, even if paraphrased slightly for clarity.

Formatting:

Glossary:

爻 should be translated as "Yáo (booleans)".

計開 means “Table of Contents”, is used as a marker to start a list of contents, can be translated as "Let's unfold our explanation."

Example

Input:

易曰。變化者。進退之象也。今編程者。罔不以變數為本。變數者何。一名命一物也。

Output:

The Book of Changes says,
"Transformation —
is the image of advance and retreat."

Now, in programming,
nothing is without variables as its foundation.

"What is a variable?"
"It is a name assigned to a thing."

Now translate the following Classical Chinese text:

{text}"""

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
    MAX_FILES_PER_RUN = 10

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
    return (
        MAX_FILES_PER_RUN,
        all_segment_files,
        segment_files,
        segment_files_to_process,
        sort_key,
    )


@app.cell
def _(
    API_DELAY_SECONDS,
    MODEL_NAME,
    TRANSLATION_PROMPT,
    client,
    mo,
    time,
    translations_dir,
):
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

            print(f"\n[{i}/{len(segment_files)}] Translating {seg_file.name}...")
            print(f"  Chinese: {chinese_text[:100]}...")

            # Prepare prompt
            prompt = TRANSLATION_PROMPT.format(text=chinese_text)

            try:
                # Call OpenAI API
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

                # Extract translation
                translation = response.choices[0].message.content.strip()

                # Save translation
                with open(trans_path, "w", encoding="utf-8") as f:
                    f.write(translation)

                print(f"✓ Saved translation: {trans_filename}")
                print(f"  Translation preview: {translation[:100]}...")

                # Wait before next API call (except for the last one)
                if i < len(segment_files):
                    time.sleep(API_DELAY_SECONDS)

            except Exception as e:
                print(f"✗ Error translating {seg_file.name}: {e}")
                # Still wait to avoid rapid retries
                if i < len(segment_files):
                    time.sleep(API_DELAY_SECONDS)

        print(f"\n✓ Completed {len(segment_files)} files. Run again to process more.")

    return (process_segments,)


@app.cell
def _(process_segments, segment_files):
    # Process each segment (already limited to MAX_FILES_PER_RUN)
    process_segments(segment_files)
    return


if __name__ == "__main__":
    app.run()
