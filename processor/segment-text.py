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
    def remove_markdown(text):
        """Remove markdown formatting from text."""
        # Remove code block markers (```...```) but keep content as plain text
        text = re.sub(r'```[\s\S]*?```', lambda m: m.group(0)[3:-3], text)

        # Remove inline code markers (`...`) but keep content
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Remove headings (# ...)
        text = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE)

        # Remove list markers (- ...) but keep the content
        text = re.sub(r'^-\s+', '', text, flags=re.MULTILINE)

        # Convert all whitespace (including newlines) to single spaces
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def split_sentences(text):
        """Split text into sentences ending with '。'"""
        # Split by '。' and keep sentences that end with it
        sentences = []
        parts = text.split('。')

        for i, part in enumerate(parts):
            part = part.strip()
            if part:
                # Add '。' back to all parts except possibly the last one
                # But since we only want sentences ending with '。', we'll add it to all
                if i < len(parts) - 1:
                    sentences.append(part + '。')
                elif text.endswith('。'):
                    # Last part and text ends with '。', so add it
                    sentences.append(part + '。')
                # If text doesn't end with '。', we skip the last part

        return [s for s in sentences if s and s.endswith('。')]

    def create_segments(sentences, min_chars=85, max_chars=95):
        """Group sentences into segments of 85-95 characters."""
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
                    segments.append(''.join(current_segment))
                    current_segment = []
                    current_length = 0
                    # Don't increment i, process this sentence again
                else:
                    # Current segment is too short, but adding would exceed max
                    # Add it anyway to avoid infinite loop, then finalize
                    current_segment.append(sentence)
                    current_length += sentence_length
                    segments.append(''.join(current_segment))
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
                        segments.append(''.join(current_segment))
                        current_segment = []
                        current_length = 0

        # Add remaining segment if any
        if current_segment:
            segments.append(''.join(current_segment))

        return segments
    return create_segments, remove_markdown, split_sentences


@app.cell
def _(create_segments, remove_markdown, split_sentences):
    def process_chapter(chapter_path, output_dir):
        """Process a single chapter file."""
        # Read the chapter
        with open(chapter_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove markdown
        text = remove_markdown(content)

        # Split into sentences
        sentences = split_sentences(text)

        # Create segments
        segments = create_segments(sentences)

        # Get chapter number from filename (e.g., "01 明義第一.md" -> "1")
        chapter_num = chapter_path.stem.split()[0]
        chapter_num = str(int(chapter_num))  # Remove leading zeros

        # Write segments to files
        for i, segment in enumerate(segments, start=1):
            output_path = output_dir / f"{chapter_num}-{i}.txt"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(segment)

        print(f"Processed {chapter_path.name}: {len(segments)} segments")
    return (process_chapter,)


@app.cell
def _(Path):
    book_dir = Path("../book")
    output_dir = Path("../segments")

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)

    # Find all markdown files in book directory
    chapter_files = sorted(book_dir.glob("*.md"))

    # Filter out non-chapter files (like README.md, LICENSE)
    chapter_files = [f for f in chapter_files if f.stem[0].isdigit()]
    return chapter_files, output_dir


@app.cell
def _(chapter_files, output_dir, process_chapter):
    # Process each chapter
    for chapter_file in chapter_files:
        process_chapter(chapter_file, output_dir)
    return


if __name__ == "__main__":
    app.run()
