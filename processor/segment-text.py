import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import re
    from pathlib import Path

    return Path, json, re


@app.cell
def _(re):
    def visible_length(text: str) -> int:
        """Count non-whitespace characters only (ignore spaces, tabs, newlines)."""
        return len(re.sub(r"\s+", "", text))

    def split_paragraphs(text):
        """Split text into paragraphs (separated by blank lines)."""
        # Split by double newlines (blank lines)
        paragraphs = re.split(r"\n\s*\n", text)
        # Filter out empty paragraphs
        return [p.strip() for p in paragraphs if p.strip()]

    def remove_markdown(text, preserve_newlines=False):
        """Remove markdown formatting from text, preserving paragraph structure.
        If preserve_newlines is True, line breaks (and exact indentation) are preserved
        for code blocks.

        Note:
        - Fenced code block markers (```...```) are handled at the paragraph
          level in process_chapter and are not stripped here.
        - Inline code spans delimited by backticks (e.g. `code`) are preserved
          verbatim so they can be handled specially downstream.
        """
        # Convert double brackets 「「　」」 to 『 』
        text = text.replace("「「", "『")
        text = text.replace("」」", "』")

        # Remove headings (# ...)
        text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)

        # Remove list markers (- ...) but keep the content
        text = re.sub(r"^-\s+", "", text, flags=re.MULTILINE)

        if preserve_newlines:
            # For code blocks, preserve newlines and the exact amount of whitespace.
            # Do not collapse multiple spaces/tabs; just return the text as-is after
            # the basic markdown cleanups above.
            return text
        else:
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
        current_length = 0  # measured using visible_length (ignoring whitespace)
        i = 0

        while i < len(sentences):
            sentence = sentences[i]
            sentence_length = visible_length(sentence)

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
                    next_sentence_length = visible_length(sentences[i])
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
def _(create_segments, json, remove_markdown, split_paragraphs, split_sentences, Path):
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
        segment_metadata = {}
        segment_counter = 1
        # Track whether we're currently inside a fenced code block (``` ... ```)
        in_code_block = False

        for paragraph in paragraphs:
            # Detect and strip fenced code markers from this paragraph, and decide if it
            # is part of a code block that may span multiple paragraphs.
            lines = paragraph.split("\n")
            fence_count = 0
            cleaned_lines = []
            for line in lines:
                if line.strip().startswith("```"):
                    fence_count += 1
                    # Skip fence lines from content
                    continue
                cleaned_lines.append(line)

            # A paragraph is a code block if we are already inside a fenced block
            # or if this paragraph starts a fenced block.
            starts_with_fence = bool(lines and lines[0].strip().startswith("```"))
            is_code_block = in_code_block or starts_with_fence

            # Toggle in_code_block if this paragraph has an odd number of fences
            if fence_count % 2 == 1:
                in_code_block = not in_code_block

            paragraph = "\n".join(cleaned_lines)

            # Skip paragraphs that are only fences / whitespace
            if not paragraph.strip():
                continue

            # Remove markdown from this paragraph
            # Preserve newlines for code blocks
            text = remove_markdown(paragraph, preserve_newlines=is_code_block)

            # Skip empty paragraphs after markdown removal
            if not text.strip():
                continue

            if is_code_block:
                # For code blocks, preserve newlines and split by newlines
                # Create segments that preserve line breaks
                lines = text.split("\n")
                # Filter out empty lines at start/end but preserve internal empty lines
                while lines and not lines[0].strip():
                    lines.pop(0)
                while lines and not lines[-1].strip():
                    lines.pop()

                # For code blocks, keep as single segment preserving all newlines
                # or split into segments if too long, but always preserve newlines
                code_text = "\n".join(lines)
                if len(code_text) <= 95:
                    # Single segment
                    paragraph_segments = [code_text]
                else:
                    # Split into multiple segments, but preserve newlines within each
                    # Split by newlines and group lines into segments
                    paragraph_segments = []
                    current_segment_lines = []
                    current_length = 0

                    for line in lines:
                        line_length = len(line) + 1  # +1 for newline
                        if current_length + line_length > 95 and current_segment_lines:
                            # Finalize current segment
                            paragraph_segments.append("\n".join(current_segment_lines))
                            current_segment_lines = [line]
                            current_length = line_length
                        else:
                            current_segment_lines.append(line)
                            current_length += line_length

                    # Add remaining segment
                    if current_segment_lines:
                        paragraph_segments.append("\n".join(current_segment_lines))
            else:
                # For regular text, split into sentences and create segments
                sentences = split_sentences(text)
                if sentences:
                    paragraph_segments = create_segments(sentences)
                else:
                    # If no sentences ending with '。', still include the text as a segment
                    # (e.g., short phrases like "乃得" that don't end with a period)
                    if text.strip():
                        paragraph_segments = [text.strip()]
                    else:
                        paragraph_segments = []

            # Track metadata for each segment from this paragraph
            for segment in paragraph_segments:
                segment_id = f"{chapter_num}-{segment_counter}"
                segment_metadata[segment_id] = {"isCodeBlock": is_code_block}
                segment_counter += 1

            all_segments.extend(paragraph_segments)

        # Write segments to files
        for i, segment in enumerate(all_segments, start=1):
            output_path = output_dir / f"{chapter_num}-{i}.txt"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(segment)

        # Write metadata JSON file for this chapter
        metadata_path = output_dir / f"{chapter_num}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(segment_metadata, f, ensure_ascii=False, indent=2)

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
