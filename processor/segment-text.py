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
def _(create_segments, json, remove_markdown, split_sentences, Path):
    def segments_exist(chapter_num, output_dir):
        """Check if segments already exist for a chapter."""
        # Check if at least one segment file exists for this chapter
        pattern = f"{chapter_num}-*.txt"
        existing_files = list(output_dir.glob(pattern))
        exists = len(existing_files) > 0
        return exists

    def process_chapter(chapter_json_path, output_dir):
        """Process a single chapter JSON file from renderer/public/chapters."""
        # Load chapter data from JSON produced by parse-markdown.py
        with open(chapter_json_path, "r", encoding="utf-8") as f:
            chapter_data = json.load(f)

        chapter_num = chapter_data.get("number")
        if chapter_num is None:
            # Fallback: derive from filename like "c1.json"
            chapter_num = int(chapter_json_path.stem.lstrip("c"))
        chapter_num = str(int(chapter_num))  # normalize

        blocks = chapter_data.get("blocks", [])

        all_segments = []
        segment_metadata: dict[str, dict[str, bool]] = {}
        segment_counter = 1

        for block in blocks:
            block_type = block.get("type")
            is_code_block = block_type == "code"
            paragraph_segments = []

            if block_type == "code":
                # Code block: source contains fenced markdown (``` ... ```).
                source = block.get("source") or ""
                lines = source.split("\n")
            cleaned_lines = []
            for line in lines:
                # Strip fence lines but keep code as-is
                if line.strip().startswith("```"):
                    continue
                cleaned_lines.append(line)

            paragraph = "\n".join(cleaned_lines)
            if not paragraph.strip():
                continue

                # Remove minimal markdown but preserve newlines/indentation
                text = remove_markdown(paragraph, preserve_newlines=True)
            if not text.strip():
                continue

                # Replicate previous code-block segmentation logic
                lines = text.split("\n")
                while lines and not lines[0].strip():
                    lines.pop(0)
                while lines and not lines[-1].strip():
                    lines.pop()

                code_text = "\n".join(lines)
                if len(code_text) <= 95:
                    paragraph_segments = [code_text] if code_text else []
                else:
                    paragraph_segments = []
                    current_segment_lines = []
                    current_length = 0

                    for line in lines:
                        line_length = len(line) + 1  # +1 for newline
                        if current_length + line_length > 95 and current_segment_lines:
                            paragraph_segments.append("\n".join(current_segment_lines))
                            current_segment_lines = [line]
                            current_length = line_length
                        else:
                            current_segment_lines.append(line)
                            current_length += line_length

                    if current_segment_lines:
                        paragraph_segments.append("\n".join(current_segment_lines))

            elif block_type == "list":
                # Reconstruct a markdown list paragraph from items so that
                # remove_markdown + sentence splitting behave as before.
                items = block.get("items") or []
                if not items:
                    continue

                paragraph_markdown = "\n".join(f"- {item}" for item in items)
                text = remove_markdown(paragraph_markdown, preserve_newlines=False)
                if not text.strip():
                    continue

                sentences = split_sentences(text)
                if sentences:
                    paragraph_segments = create_segments(sentences)
                else:
                    if text.strip():
                        paragraph_segments = [text.strip()]

            else:
                # Plain text block
                source = block.get("source") or ""
                paragraph = source
                if not paragraph.strip():
                    continue

                text = remove_markdown(paragraph, preserve_newlines=False)
                if not text.strip():
                    continue

                sentences = split_sentences(text)
                if sentences:
                    paragraph_segments = create_segments(sentences)
                else:
                    if text.strip():
                        paragraph_segments = [text.strip()]

            # Track metadata for each segment from this block
            for segment in paragraph_segments:
                segment_id = f"{chapter_num}-{segment_counter}"
                segment_metadata[segment_id] = {"isCodeBlock": is_code_block}
                segment_counter += 1
                all_segments.append(segment)

        # Write segments to files
        for i, segment in enumerate(all_segments, start=1):
            output_path = output_dir / f"{chapter_num}-{i}.txt"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(segment)

        # Write metadata JSON file for this chapter
        metadata_path = output_dir / f"{chapter_num}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(segment_metadata, f, ensure_ascii=False, indent=2)

        print(f"Processed {chapter_json_path.name}: {len(all_segments)} segments")

    return process_chapter, segments_exist


@app.cell
def _(Path):
    chapters_dir = Path("../renderer/public/chapters").resolve()
    output_dir = Path("../renderer/public/segments").resolve()

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)

    # Find all chapter JSON files
    chapter_files = sorted(chapters_dir.glob("c*.json"))
    return chapter_files, output_dir


@app.cell
def _(chapter_files, json, output_dir, process_chapter, segments_exist):
    # Process each chapter JSON
    for chapter_file in chapter_files:
        with open(chapter_file, "r", encoding="utf-8") as f:
            chapter_data = json.load(f)

        chapter_num = chapter_data.get("number")
        if chapter_num is None:
            chapter_num = int(chapter_file.stem.lstrip("c"))
        chapter_num = str(int(chapter_num))

        # Check if segments already exist
        if segments_exist(chapter_num, output_dir):
            existing_files = list(output_dir.glob(f"{chapter_num}-*.txt"))
            print(
                f"Skipping {chapter_file.name}: {len(existing_files)} segment files already exist"
            )
            continue

        print(f"Processing {chapter_file.name} (chapter {chapter_num})...")
        process_chapter(chapter_file, output_dir)
    return


if __name__ == "__main__":
    app.run()
