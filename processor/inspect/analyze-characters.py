import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    from pathlib import Path
    from collections import Counter

    return Counter, Path, json


@app.cell
def _(Path):
    Path(__file__)
    return


@app.cell
def _(Path):
    CHAPTERS_DIR = (
        Path(__file__).parent.parent.parent / "renderer" / "public" / "chapters"
    )
    return (CHAPTERS_DIR,)


@app.cell
def _(CHAPTERS_DIR):
    # Load all chapter files
    chapter_files = sorted(CHAPTERS_DIR.glob("c*.json"))
    print(f"Found {len(chapter_files)} chapter files")
    return (chapter_files,)


@app.cell
def _(chapter_files, json):
    # Extract all source text from chapters
    all_text = []
    chapter_data = []

    for chapter_file in chapter_files:
        with open(chapter_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            chapter_data.append(data)

            # Extract source text from all blocks
            for block in data.get("blocks", []):
                source = block.get("source")
                if source:
                    all_text.append(source)

                # Also check items in list blocks
                items = block.get("items")
                if items:
                    for item in items:
                        if isinstance(item, str):
                            all_text.append(item)

    combined_text = "".join(all_text)
    print(f"Total characters extracted: {len(combined_text)}")
    return chapter_data, combined_text


@app.cell
def _(Counter, combined_text):
    # Character statistics
    char_counter = Counter(combined_text)
    unique_chars = len(char_counter)
    total_chars = len(combined_text)

    print(f"Total characters: {total_chars:,}")
    print(f"Unique characters: {unique_chars:,}")
    return char_counter, total_chars, unique_chars


@app.cell
def _(char_counter, total_chars):
    # Most common characters
    most_common = char_counter.most_common(50)
    print("\nTop 50 most common characters:")
    for char, count in most_common:
        percentage = (count / total_chars) * 100
        print(f"  {char}: {count:,} ({percentage:.2f}%)")
    return


@app.cell
def _(char_counter, total_chars):
    # Character frequency table (all characters)
    char_freq_data = [
        {"character": char, "count": count, "percentage": (count / total_chars) * 100}
        for char, count in char_counter.most_common()
    ]
    char_freq_data[:20]  # Show top 20
    return


@app.function
# Filter Chinese characters (CJK Unified Ideographs)
def is_chinese_char(char):
    """Check if character is a Chinese character"""
    return "\u4e00" <= char <= "\u9fff"


@app.cell
def _(Counter, char_counter):
    chinese_chars = {
        char: count for char, count in char_counter.items() if is_chinese_char(char)
    }
    chinese_counter = Counter(chinese_chars)

    print(f"Chinese characters: {len(chinese_counter):,}")
    print(f"Non-Chinese characters: {len(char_counter) - len(chinese_counter):,}")
    return (chinese_counter,)


@app.cell
def _(chinese_counter):
    # Most common Chinese characters
    chinese_most_common = chinese_counter.most_common(50)
    chinese_total = sum(chinese_counter.values())

    print("\nTop 50 most common Chinese characters:")
    for chr, cnt in chinese_most_common:
        p = (cnt / chinese_total) * 100
        print(f"  {chr}: {cnt:,} ({p:.2f}%)")
    return (chinese_total,)


@app.cell
def _(chinese_counter, chinese_total):
    # Chinese character frequency table
    chinese_freq_data = [
        {"character": char, "count": count, "percentage": (count / chinese_total) * 100}
        for char, count in chinese_counter.most_common()
    ]
    chinese_freq_data[:30]  # Show top 30 Chinese characters
    return


@app.cell
def _(Counter, char_counter):
    # Filter non-Chinese characters
    non_chinese_chars = {
        char: count for char, count in char_counter.items() if not is_chinese_char(char)
    }
    non_chinese_counter = Counter(non_chinese_chars)

    print(f"Non-Chinese characters: {len(non_chinese_counter):,}")
    print(f"Total non-Chinese character count: {sum(non_chinese_counter.values()):,}")
    return (non_chinese_counter,)


@app.cell
def _(non_chinese_counter):
    # Most common non-Chinese characters
    non_chinese_most_common = non_chinese_counter.most_common(50)
    non_chinese_total = sum(non_chinese_counter.values())

    print("\nTop 50 most common non-Chinese characters:")
    for nc_char, nc_count in non_chinese_most_common:
        nc_percentage = (nc_count / non_chinese_total) * 100
        # Show character representation (escape if needed)
        char_repr = (
            repr(nc_char)
            if nc_char in ["\n", "\t", " "] or ord(nc_char) < 32
            else nc_char
        )
        print(f"  {char_repr}: {nc_count:,} ({nc_percentage:.2f}%)")
    return (non_chinese_total,)


@app.cell
def _(non_chinese_counter, non_chinese_total):
    # Non-Chinese character frequency table
    non_chinese_freq_data = [
        {
            "character": (
                repr(char) if char in ["\n", "\t", " "] or ord(char) < 32 else char
            ),
            "count": count,
            "percentage": (count / non_chinese_total) * 100,
        }
        for char, count in non_chinese_counter.most_common()
    ]
    non_chinese_freq_data[:30]  # Show top 30 non-Chinese characters
    return


@app.cell
def _(Counter, chapter_data, chapter_files):
    # Character distribution by chapter
    chapter_stats = []

    for ch_file, ch_data in zip(chapter_files, chapter_data):
        chapter_text = []
        for ch_block in ch_data.get("blocks", []):
            ch_source = ch_block.get("source")
            if ch_source:
                chapter_text.append(ch_source)
            ch_items = ch_block.get("items")
            if ch_items:
                for ch_item in ch_items:
                    if isinstance(ch_item, str):
                        chapter_text.append(ch_item)

        chapter_combined = "".join(chapter_text)
        chapter_char_counter = Counter(chapter_combined)
        chapter_chinese_chars = {
            char: count
            for char, count in chapter_char_counter.items()
            if is_chinese_char(char)
        }

        chapter_stats.append(
            {
                "chapter": ch_data.get("id", "unknown"),
                "title": ch_data.get("title", ""),
                "total_chars": len(chapter_combined),
                "unique_chars": len(chapter_char_counter),
                "unique_chinese_chars": len(chapter_chinese_chars),
                "chinese_char_count": sum(chapter_chinese_chars.values()),
            }
        )

    # Display chapter statistics
    print("Chapter Statistics:")
    print(
        f"{'Chapter':<10} {'Title':<15} {'Total Chars':<15} {'Unique Chars':<15} {'Unique Chinese':<15} {'Chinese Count':<15}"
    )
    print("-" * 90)
    for stat in chapter_stats:
        print(
            f"{stat['chapter']:<10} {stat['title']:<15} {stat['total_chars']:<15} {stat['unique_chars']:<15} {stat['unique_chinese_chars']:<15} {stat['chinese_char_count']:<15}"
        )
    return (chapter_stats,)


@app.cell
def _(
    chapter_files,
    chapter_stats,
    chinese_counter,
    total_chars,
    unique_chars,
):
    # Summary statistics
    print("=== Summary Statistics ===")
    print(f"\nTotal chapters analyzed: {len(chapter_files)}")
    print(f"Total characters: {total_chars:,}")
    print(f"Unique characters: {unique_chars:,}")
    print(f"Unique Chinese characters: {len(chinese_counter):,}")
    avg_chars_per_chapter = total_chars / len(chapter_files)
    avg_unique_chinese = sum(s["unique_chinese_chars"] for s in chapter_stats) / len(
        chapter_stats
    )
    print(f"\nAverage characters per chapter: {avg_chars_per_chapter:,.0f}")
    print(f"Average unique Chinese characters per chapter: {avg_unique_chinese:.0f}")
    return


if __name__ == "__main__":
    app.run()
