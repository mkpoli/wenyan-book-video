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


TRANSLATION_PROMPT = """You are to translate Classical Chinese prose (especially technical or literary works such as guides for the Wenyan programming language) into refined, natural English without omitting classical nuance.

Follow these formatting and stylistic rules carefully.

## Translation Rules

### Preserve Original Structure
- Each 。 (full stop) in the original Chinese already marks one canonical sentence.
- For this task, **each input Chinese sentence must map to exactly one English line**.
- Do NOT merge or split sentences; keep 1:1 mapping between input sentences and output lines.
- Retain quotation marks (「」『』) and render them faithfully using English typographical quotes (“”).
- Add proper English punctuation (period, comma, semicolon, colon, dash etc.) to the translation according to the context.

### Maintain Classical Tone
- Use dignified, reflective, and occasionally poetic phrasing suitable for a didactic text.
- Avoid modern or casual diction.
- Strive for clarity while maintaining the philosophical rhythm and rhetorical symmetry of Classical Chinese.

### No Omission or Summarization
- Every clause and metaphor must appear in the translation, even if slightly paraphrased for clarity.
- Preserve original meaning and sentence order exactly.

### English Formatting
- Each sentence begins on a new line.
- Output plain text only inside the JSON values (no Markdown).
- Keep all nested quotations and rhetorical questions intact.
- Use typographical punctuation (— … “” ‘ ’) where natural.

## Glossary (for meaning consistency, not literal word-for-word mapping)
- “計開” → “Table of Contents”, “Let us unfold our explanation.”, “As follows,”, or “Let us begin.” depending on context.
- “至此畧備矣” → “Thus it is now briefly complete.”
- “書之” → “Write it down.”
- “數” → “Numbers (numerals)”.
- “言” → “Words (strings)”.
- “爻” → “Yáo (booleans)”.
- “列” → “Lists (arrays)”.
- “物” → “Things (objects)”.
- “術” → “Means (methods)”.
- “甲” → “A”, “乙” → “B”, “丙” → “C”, etc.

## Your Task

You will receive multiple short Chinese sentences, each with a unique `id`.

Return ONLY valid JSON of the form:

  {{
    "translations": [
      {{"id": "<sentence-id>", "translation": "<English line>"}},
      ...
    ]
  }}

Rules for the JSON:
- The `translations` array must contain one entry for every input sentence.
- Each `translation` value must be a single line of English text for that sentence.
- Do NOT include any comments or text outside the JSON.
- Do NOT include trailing commas.

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
        lines.append(source)
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

    print(f"  🤖 Translating {len(batch_ids)} sentence(s)...")

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert translator specializing in Classical Chinese "
                    "to English translation, particularly for technical and literary works."
                ),
            },
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
