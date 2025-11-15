import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI


MODEL_NAME = "gpt-5-nano"
API_DELAY_SECONDS = 1.0  # Small delay between batches
MAX_SENTENCES_PER_BATCH = 30
MAX_CHARS_PER_BATCH = 2000


TRANSLATION_PROMPT = """The following is requirements for a translation task. Follow these rules carefully and operate accordingly.

## Target

From: Traditional Classical Chinese (文言文/漢文) written in modern era.
To: Modern or Contemporary English
Subject: Modern technical text (a introductory handbook)
Topic: Programming basics and a programming language called Wenyan (world's first Classical Chinese-styled programming language) 

## English Style
- Use dignified, reflective, refined, natural, antique-feeling, recondite, rhythmic, and occasionally poetic and philosophical phrasing suitable for a didactic text with full classical nuance.
- Strive for clarity while maintaining the philosophical rhythm and rhetorical symmetry, phonetic harmony and balance of Classical Chinese.
- Add proper and old-style, typographical English punctuations (period, comma, semicolon, colon, dash, quotation marks: 「」→“”, 『』→‘’, etc.) inside the same line only according to the context.
- Output plain text only available in Unicode.

## Consistency
- Each Chinese sentence ends with 。 -> one English line (no line-breaking). Keep strict 1:1 mapping: no merging, no splitting, no reordering, no omission, authentic and faithful as possible without hurting the natural flow and clarity.
- Equivalent of comma and period in English are all marked with “。”, so potentially two or more Chinese sentences may be mapped to one English line.
    - X者。 = topic (“As for X—”, “‘X,’ —”, etc.)
    - X者。Y也。 = two lines: topic → explanation. (["A者。", "B也。"] -> ["A —", "is B"] etc.) h
    - 夫X者。……。 = “Speaking of/Regarding/About X,…”
- Keep all nested quotations and rhetorical questions, metaphors intact if possible.
- Use typographical punctuation (— , ; … “” ‘ ’) where natural.

## Glossary
Use below for meaning consistency, but be flexible and accommdating, not literal word-for-word mapping, adjust depending on context.
- “計開” → means “Table of Contents”, used as “As follows,”, or “Let us begin.”, can be translated as  “Let us unfold our explanation.”, .
- “至此畧備矣” → “Thus it is now briefly complete.”
- After a question, “耶。” or “乎。”, usually there will be a follow-up answer witf “曰。”, translate it as “It is answered,” or a like.

### Code
- “甲” → “A”, “乙” → “B”, “丙” → “C”, “丁” → “D”, “戊” → “E”, “己” → “F”, “庚” → “G”, “辛” → “H”, “壬” → “I”, “癸” → “J”, etc.
- “書之” → “Write it down.”
- “云云。” → “Thus and thus.” (“……云云。” → “And alike”, “like ……”, “beginning with ……”, etc.)
- Classes:
    - “數” → “Numbers (numerals)”.
    - “言” → “Words (strings)”.
    - “爻” → “Yáo (booleans)”.
    - “列” → “Lists (arrays)”.
    - “物” → “Things (objects)”.
    - “術” → “Means (methods)”.
    - “吾有一言。曰『……』。名之曰……。” → “I have a word.” “It says, ‘……’.”; Name it ‘……’.”
    - “有數九。名之曰「……」” -> “There are a number of nine.” “It is named ‘……’.”
- Loops
    - “循環” → “Loops”, “Looping”
    - “恆為是。” → “Constantly do this.”
    - “為是百遍。” → “Do this one hundred times.”


## Output

You will receive multiple short Chinese sentences, each with a unique `id`. Return ONLY valid JSON of the form no extra text, comments, trailing commas, etc.

  {{
    "translations": [
      {{"id": "<sentence-id>", "translation": "<English line>"}},
      ...
    ]
  }}

## Examples

易曰。變化者。進退之象也。今編程者。罔不以變數為本。變數者何。一名命一物也。

{{
  "translations": 
    [
        {{"id": "c2-s1", "translation":"The Book of Changes says,"}},
        {{"id": "c2-s2", "translation":""Transformation —"}},
        {{"id": "c2-s3"," translation":""is the image of advance and retreat.""}},
        {{"id": "c2-s4", "translation":"Now, in programming,"}},
        {{"id": "c2-s5", "translation":"nothing is without variables as its foundation."}},
        {{"id": "c2-s6", "translation":""What is a variable?""}},
        {{"id": "c2-s7", "translation":""It is a name assigned to a thing.""}}
    ]
}}

編程者何。所以役機器也。機器者何。所以代人力也。然機器之力也廣。其算也速。唯智不逮也。故有智者慎謀遠慮。下筆千言。如軍令然。如藥方然。謂之程式。機器既明之。乃能為人所使。或演星文。或析事理。

{{
  "translations": 
    [
        {{"id": "c1-s1", "translation":"What is programming?"}},
        {{"id": "c1-s2", "translation":"That by which one commands machines."}},
        {{"id": "c1-s3", "translation":"What is a machine?"}},
        {{"id": "c1-s4", "translation":"That by which human labor is replaced."}},
        {{"id": "c1-s5", "translation":"Yet the power of machines is vast,"}},
        {{"id": "c1-s6", "translation":"their calculations swift,"}},
        {{"id": "c1-s7", "translation":"but their wisdom does not reach that of man."}},
        {{"id": "c1-s8", "translation":"Therefore, the wise plan with care and foresight."}},
        {{"id": "c1-s9", "translation":"They set down a thousand words,"}},
        {{"id": "c1-s10", "translation":"as if issuing military orders,"}},
        {{"id": "c1-s11", "translation":"as if prescribing medicine —"}},
        {{"id": "c1-s12", "translation":"this is called a program."}},
        {{"id": "c1-s13", "translation":"Once the machine comprehends it,"}},
        {{"id": "c1-s14", "translation":"it can then be made to serve mankind —"}},
        {{"id": "c1-s15", "translation":"to chart the movements of the stars,"}},
        {{"id": "c1-s16", "translation":"or to analyze the patterns of reason."}}
    ]
}}

## Your Task

Now translate the following sentences:

{text}
"""


def _sort_chapter_sentences_file(path: Path) -> int:
    """
    Sort key for 'c1.sentences.json' -> 1, etc.
    """
    name = path.stem.split(".")[0]  # "c1"
    num_str = name.lstrip("c")
    return int(num_str) if num_str.isdigit() else 0


def _sentence_sort_key(sent_id: str) -> int:
    """
    Sort key for sentence ids like 'c1-s245' -> 245.
    """
    if "-s" in sent_id:
        try:
            return int(sent_id.split("-s", 1)[1])
        except ValueError:
            return 0
    return 0


def _load_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set. "
            "Please set it in your .env file or environment."
        )
    return OpenAI(api_key=api_key)


def _prepare_translation_files(
    sentences_dir: Path,
    translations_dir: Path,
) -> List[Tuple[Path, Path]]:
    """
    For each `cN.sentences.json`, ensure a corresponding
    `cN.translations.json` exists, initialized with:

      { "cN-sK": { "source": "...", "translation": "" }, ... }

    Returns a list of (sentences_path, translations_path) pairs.
    """
    translations_dir.mkdir(exist_ok=True, parents=True)

    chapter_pairs: List[Tuple[Path, Path]] = []

    for sentences_path in sorted(
        sentences_dir.glob("c*.sentences.json"), key=_sort_chapter_sentences_file
    ):
        chapter_id = sentences_path.stem.split(".")[0]  # "c1"
        translations_path = translations_dir / f"{chapter_id}.translations.json"

        if not translations_path.exists():
            canon = json.loads(sentences_path.read_text(encoding="utf-8"))
            init_data: Dict[str, Dict[str, str]] = {}

            for s in canon.get("sentences", []):
                sid = s.get("id")
                src = s.get("source", "")
                if not isinstance(sid, str) or not isinstance(src, str):
                    continue
                init_data[sid] = {"source": src, "translation": ""}

            translations_path.write_text(
                json.dumps(init_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Created {translations_path}")

        chapter_pairs.append((sentences_path, translations_path))

    print(f"Prepared {len(chapter_pairs)} sentence translation files")
    return chapter_pairs


def _build_batches_for_chapter(
    translations_data: Dict[str, Dict[str, str]],
) -> List[List[str]]:
    """
    Build batches of sentence ids that are missing translation.
    Batches are constrained by MAX_SENTENCES_PER_BATCH and MAX_CHARS_PER_BATCH.
    """
    missing_ids = [
        sid
        for sid in sorted(translations_data.keys(), key=_sentence_sort_key)
        if not translations_data.get(sid, {}).get("translation", "").strip()
    ]

    batches: List[List[str]] = []
    current: List[str] = []
    current_chars = 0

    for sid in missing_ids:
        source = translations_data[sid].get("source", "")
        length = len(source)

        if current and (
            len(current) >= MAX_SENTENCES_PER_BATCH
            or current_chars + length > MAX_CHARS_PER_BATCH
        ):
            batches.append(current)
            current = []
            current_chars = 0

        current.append(sid)
        current_chars += length

    if current:
        batches.append(current)

    return batches


def _build_text_block_for_batch(
    translations_data: Dict[str, Dict[str, str]],
    batch_ids: List[str],
) -> str:
    """
    Build the `{text}` payload inserted into TRANSLATION_PROMPT for one batch.
    """
    lines: List[str] = []
    for idx, sid in enumerate(batch_ids, start=1):
        source = translations_data[sid].get("source", "")
        lines.append(f"SENTENCE {idx}: {sid}")
        lines.append(source.strip())
        lines.append("")  # blank line between sentences
    return "\n".join(lines).strip()


def _call_translation_api(
    client: OpenAI,
    batch_ids: List[str],
    translations_data: Dict[str, Dict[str, str]],
) -> Dict[str, str]:
    """
    Call the model for one batch of sentence ids.
    Returns a mapping {sent_id: translated_line}.
    """
    text_block = _build_text_block_for_batch(translations_data, batch_ids)
    prompt = TRANSLATION_PROMPT.format(text=text_block)
    system_content = (
        "You are an expert translator specializing in Classical Chinese "
        "to English translation, particularly for technical and literary works."
    )

    # Debug: print exact prompt with separators
    print("\n" + "=" * 80)
    print("DEBUG: System Message")
    print("=" * 80)
    print(system_content)
    print("\n" + "=" * 80)
    print("DEBUG: User Prompt (Exact)")
    print("=" * 80)
    print(prompt)
    print("=" * 80 + "\n")

    print(f"  🤖 Translating {len(batch_ids)} sentence(s)...")

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ],
    )

    raw = (response.choices[0].message.content or "").strip()
    print("  📦 Raw response preview:")
    print(f"     {raw[:200]}..." if len(raw) > 200 else f"     {raw}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON from model response: {exc}") from exc

    translations_list = payload.get("translations")
    if not isinstance(translations_list, list):
        raise RuntimeError(
            "Model response JSON does not contain a 'translations' list."
        )

    result: Dict[str, str] = {}
    for entry in translations_list:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("id")
        t = entry.get("translation")
        if isinstance(sid, str) and isinstance(t, str):
            result[sid] = t.strip()

    missing = [sid for sid in batch_ids if sid not in result]
    if missing:
        raise RuntimeError(
            f"Missing translations for sentence(s): {', '.join(missing)}"
        )

    return result


def _translate_chapter(
    client: OpenAI,
    sentences_path: Path,
    translations_path: Path,
) -> None:
    """
    Translate all missing sentences in one chapter's translations file.
    """
    chapter_id = sentences_path.stem.split(".")[0]  # "c1"
    print("\n" + "=" * 80)
    print(f"Translating sentence file: {chapter_id}")
    print("=" * 80)

    translations_data: Dict[str, Dict[str, str]] = json.loads(
        translations_path.read_text(encoding="utf-8")
    )

    batches = _build_batches_for_chapter(translations_data)
    if not batches:
        print("  ✓ No missing translations; nothing to do.")
        return

    print(
        f"  Found {sum(len(b) for b in batches)} missing sentence(s) "
        f"in {len(batches)} batch(es)."
    )

    changed = False

    try:
        for batch_idx, batch_ids in enumerate(batches, start=1):
            print(f"\n  Batch {batch_idx}/{len(batches)}: {len(batch_ids)} sentence(s)")
            try:
                batch_translations = _call_translation_api(
                    client, batch_ids, translations_data
                )
            except Exception as exc:
                print(f"  ❌ Error translating batch {batch_idx}: {exc}")
                # Save partial progress before breaking
                if changed:
                    translations_path.write_text(
                        json.dumps(translations_data, ensure_ascii=False, indent=2)
                        + "\n",
                        encoding="utf-8",
                    )
                    print(f"  ✓ Saved partial progress: {translations_path.name}")
                break

            for sid, eng in batch_translations.items():
                entry = translations_data.get(sid) or {}
                entry["translation"] = eng
                translations_data[sid] = entry
                preview = eng[:60] + ("..." if len(eng) > 60 else "")
                print(f"    💾 {sid}: {preview}")
                changed = True

            # Save after each batch so progress isn't lost on interruption
            if changed:
                translations_path.write_text(
                    json.dumps(translations_data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"  ✓ Saved progress after batch {batch_idx}")

            print(f"  ⏳ Waiting {API_DELAY_SECONDS:.1f}s before next batch...")
            time.sleep(API_DELAY_SECONDS)
    except KeyboardInterrupt:
        # User interrupted (Ctrl+C); save what we have
        if changed:
            translations_path.write_text(
                json.dumps(translations_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"\n  ✓ Saved partial progress before exit: {translations_path.name}")
        print("\n  ↯ Interrupted by user; stopping translation.")
        raise SystemExit(0)

    if changed:
        print(f"\n  ✓ Completed all batches for {translations_path.name}")
    else:
        print("\n  ✓ No changes made for this chapter.")


def main() -> None:
    root = Path(__file__).resolve().parents[1]  # processor/ -> project root
    sentences_dir = (root / "renderer" / "public" / "sentences").resolve()
    translations_dir = (root / "renderer" / "public" / "translations").resolve()

    if not sentences_dir.exists():
        raise SystemExit(f"Sentences directory not found: {sentences_dir}")

    client = _load_client()
    chapter_pairs = _prepare_translation_files(sentences_dir, translations_dir)

    wanted: List[str] = []
    if len(sys.argv) > 1:
        wanted = list(sys.argv[1:])

    for sentences_path, translations_path in chapter_pairs:
        chapter_id = sentences_path.stem.split(".")[0]  # "c1"
        if wanted and chapter_id not in wanted:
            continue
        _translate_chapter(client, sentences_path, translations_path)

    print("\nAll done.")


if __name__ == "__main__":
    main()
