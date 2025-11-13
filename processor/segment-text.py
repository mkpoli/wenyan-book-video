import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import re
    from pathlib import Path

    return Path, re


@app.cell
def _(re):
    def split_paragraphs(text):
        """Split text into paragraphs (separated by blank lines)."""
        # Split by double newlines (blank lines)
        paragraphs = re.split(r"\n\s*\n", text)
        # Filter out empty paragraphs
        return [p.strip() for p in paragraphs if p.strip()]

    def remove_markdown(text):
        """Remove markdown formatting from text, preserving paragraph structure."""
        # Convert double brackets 「「　」」 to 『 』
        text = text.replace("「「", "『")
        text = text.replace("」」", "』")

        # Remove code block markers (```...```) but keep content as plain text
        text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0)[3:-3], text)

        # Remove inline code markers (`...`) but keep content
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Remove headings (# ...)
        text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)

        # Remove list markers (- ...) but keep the content
        text = re.sub(r"^-\s+", "", text, flags=re.MULTILINE)

        # Convert multiple whitespace (but preserve single newlines within paragraph)
        # Replace multiple spaces/tabs with single space
        text = re.sub(r"[ \t]+", " ", text)
        # Replace multiple newlines with single space (paragraph boundaries already split)
        text = re.sub(r"\n+", " ", text)

        return text.strip()

    def split_sentences(text):
        """Split text into sentences ending with '。'"""
        # Split by '。' and keep sentences that end with it
        sentences = []
        parts = text.split("。")

        for i, part in enumerate(parts):
            part = part.strip()
            if part:
                # Add '。' back to all parts except possibly the last one
                # But since we only want sentences ending with '。', we'll add it to all
                if i < len(parts) - 1:
                    sentences.append(part + "。")
                elif text.endswith("。"):
                    # Last part and text ends with '。', so add it
                    sentences.append(part + "。")
                # If text doesn't end with '。', we skip the last part

        return [s for s in sentences if s and s.endswith("。")]

    def create_segments(sentences, min_chars=85, max_chars=95):
        """Group sentences into segments of 85-95 characters.
        This function processes sentences within a single paragraph only."""
        segments = []
        current_segment = []
        current_length = 0
        i = 0

        while i < len(sentences):
            sentence = sentences[i]
            sentence_length = len(sentence)

            # If current segment is empty, start with this sentence
            if not current_segment:
                current_segment.append(sentence)
                current_length = sentence_length
                i += 1
                continue

            # Check if adding this sentence would exceed max
            if current_length + sentence_length > max_chars:
                # If current segment is already at least min_chars, finalize it
                if current_length >= min_chars:
                    segments.append("".join(current_segment))
                    current_segment = []
                    current_length = 0
                    # Don't increment i, process this sentence again
                else:
                    # Current segment is too short, but adding would exceed max
                    # Add it anyway to avoid infinite loop, then finalize
                    current_segment.append(sentence)
                    current_length += sentence_length
                    segments.append("".join(current_segment))
                    current_segment = []
                    current_length = 0
                    i += 1
            else:
                # Can add this sentence
                current_segment.append(sentence)
                current_length += sentence_length
                i += 1

                # If we're in the target range and next sentence would push us over,
                # consider finalizing (but only if we have more sentences)
                if current_length >= min_chars and i < len(sentences):
                    next_sentence_length = len(sentences[i])
                    if current_length + next_sentence_length > max_chars:
                        segments.append("".join(current_segment))
                        current_segment = []
                        current_length = 0

        # Add remaining segment if any
        if current_segment:
            segments.append("".join(current_segment))

        return segments

    return create_segments, remove_markdown, split_paragraphs, split_sentences


@app.cell
def _(create_segments, remove_markdown, split_paragraphs, split_sentences, Path):
    def segments_exist(chapter_num, output_dir):
        """Check if segments already exist for a chapter."""
        # Check if at least one segment file exists for this chapter
        pattern = f"{chapter_num}-*.txt"
        existing_files = list(output_dir.glob(pattern))
        exists = len(existing_files) > 0
        return exists

    def process_chapter(chapter_path, output_dir):
        """Process a single chapter file, respecting paragraph boundaries."""
        # Get chapter number from filename (e.g., "01 明義第一.md" -> "1")
        chapter_num = chapter_path.stem.split()[0]
        chapter_num = str(int(chapter_num))  # Remove leading zeros

        # Read the chapter
        with open(chapter_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split into paragraphs first (before removing markdown)
        paragraphs = split_paragraphs(content)

        # Process each paragraph separately
        all_segments = []
        for paragraph in paragraphs:
            # Remove markdown from this paragraph
            text = remove_markdown(paragraph)

            # Skip empty paragraphs
            if not text.strip():
                continue

            # Split into sentences within this paragraph
            sentences = split_sentences(text)

            # Create segments within this paragraph only
            # (sentences from different paragraphs will never be combined)
            paragraph_segments = create_segments(sentences)
            all_segments.extend(paragraph_segments)

        # Write segments to files
        for i, segment in enumerate(all_segments, start=1):
            output_path = output_dir / f"{chapter_num}-{i}.txt"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(segment)

        print(f"Processed {chapter_path.name}: {len(all_segments)} segments")

    return process_chapter, segments_exist


@app.cell
def _(Path):
    book_dir = Path("../book").resolve()
    output_dir = Path("../renderer/public/segments").resolve()

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)

    # Find all markdown files in book directory
    chapter_files = sorted(book_dir.glob("*.md"))

    # Filter out non-chapter files (like README.md, LICENSE)
    chapter_files = [f for f in chapter_files if f.stem[0].isdigit()]
    return chapter_files, output_dir


@app.cell
def _(chapter_files, output_dir, process_chapter, segments_exist):
    # Process each chapter
    for chapter_file in chapter_files:
        # Get chapter number from filename (e.g., "01 明義第一.md" -> "1")
        chapter_num = chapter_file.stem.split()[0]
        chapter_num = str(int(chapter_num))  # Remove leading zeros

        # Check if segments already exist
        pattern = f"{chapter_num}-*.txt"
        existing_files = list(output_dir.glob(pattern))
        if existing_files:
            print(
                f"Skipping {chapter_file.name}: {len(existing_files)} segment files already exist"
            )
            continue

        print(f"Processing {chapter_file.name} (chapter {chapter_num})...")
        process_chapter(chapter_file, output_dir)
    return


if __name__ == "__main__":
    app.run()
