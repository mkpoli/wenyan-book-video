import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from any_llm import completion


def _load_translation_config() -> tuple[str, str, str]:
    """
    Load translation configuration from translate.toml.
    Returns (model_name, system_prompt, translation_prompt) tuple.
    Raises ValueError if config file is missing, invalid, or required fields are missing.
    """
    config_path = Path(__file__).resolve().parent / "translate.toml"

    if not config_path.exists():
        raise ValueError(
            f"Translation config file not found: {config_path}. "
            "Please create translate.toml in the processor directory."
        )

    try:
        with config_path.open("rb") as f:
            cfg = tomllib.load(f)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Failed to parse translation config {config_path}: {exc}"
        ) from exc

    table = cfg.get("translation")
    if not isinstance(table, dict):
        raise ValueError(
            f"Config file {config_path} must contain a [translation] section"
        )

    model_name = table.get("model_name")
    system_prompt = table.get("system_prompt")
    translation_prompt = table.get("translation_prompt")

    if not isinstance(model_name, str):
        raise ValueError(
            f"Config file {config_path} must have 'model_name' as a string in [translation] section"
        )

    if not isinstance(translation_prompt, str):
        raise ValueError(
            f"Config file {config_path} must have 'translation_prompt' as a string in [translation] section"
        )

    if not isinstance(system_prompt, str):
        raise ValueError(
            f"Config file {config_path} must have 'system_prompt' as a string in [translation] section"
        )

    if "{text}" not in translation_prompt:
        raise ValueError(
            f"Config file {config_path} translation_prompt must contain {{text}} placeholder"
        )

    return model_name, system_prompt, translation_prompt


# Load configuration from file (required)
MODEL_NAME, SYSTEM_PROMPT, TRANSLATION_PROMPT = _load_translation_config()

API_DELAY_SECONDS = 1.0  # Small delay between batches
MAX_SENTENCES_PER_BATCH = 30
MAX_CHARS_PER_BATCH = 2000
MAX_CONTEXT_CHARS = 1800
MAX_FUTURE_CONTEXT_CHARS = 500


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


def _setup_any_llm() -> None:
    load_dotenv()
    # any-llm will automatically pick up API keys from environment variables
    # e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
    # api_key = os.getenv("OPENAI_API_KEY")
    # if not api_key:
    #     raise ValueError(
    #         "OPENAI_API_KEY environment variable not set. "
    #         "Please set it in your .env file or environment."
    #     )
    # return OpenAI(api_key=api_key)
    pass


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


def _collect_previous_context(
    translations_data: Dict[str, Dict[str, str]],
    batch_ids: List[str],
    max_chars: int = MAX_CONTEXT_CHARS,
) -> Tuple[str, str]:
    """
    Gather concatenated prior sentence sources and translations to seed the prompt.
    Only sentences that occur before the current batch (and that have translations)
    are included, up to `max_chars` combined characters.
    """

    if not batch_ids:
        return "", ""

    ordered_ids = sorted(translations_data.keys(), key=_sentence_sort_key)
    try:
        first_batch_index = ordered_ids.index(batch_ids[0])
    except ValueError:
        return "", ""

    context_ids = ordered_ids[:first_batch_index]
    collected: List[Tuple[str, str]] = []
    running_chars = 0

    for sid in reversed(context_ids):
        entry = translations_data.get(sid) or {}
        source = (entry.get("source") or "").strip()
        translation = (entry.get("translation") or "").strip()

        if not source and not translation:
            continue

        addition = len(source) + len(translation)
        if addition == 0:
            continue

        if running_chars + addition > max_chars:
            break

        collected.append((source, translation))
        running_chars += addition

    if not collected:
        return "", ""

    collected.reverse()
    sentences_context = " ".join(src for src, _ in collected if src).strip()
    translations_context = " ".join(tr for _, tr in collected if tr).strip()

    return sentences_context, translations_context


def _collect_future_context(
    translations_data: Dict[str, Dict[str, str]],
    batch_ids: List[str],
    max_chars: int = MAX_FUTURE_CONTEXT_CHARS,
) -> str:
    """
    Gather upcoming sentence sources for future context to guide translation.
    Only returns source text, as translations don't exist yet.
    """
    if not batch_ids:
        return ""

    ordered_ids = sorted(translations_data.keys(), key=_sentence_sort_key)
    try:
        # Find index of the last item in the current batch
        last_batch_index = ordered_ids.index(batch_ids[-1])
    except ValueError:
        return ""

    # Check indices after the batch
    context_ids = ordered_ids[last_batch_index + 1 :]
    collected: List[str] = []
    running_chars = 0

    for sid in context_ids:
        entry = translations_data.get(sid) or {}
        source = (entry.get("source") or "").strip()
        if not source:
            continue

        length = len(source)
        if running_chars + length > max_chars:
            break

        collected.append(source)
        running_chars += length

    if not collected:
        return ""

    return " ".join(collected).strip()


def _build_text_block_for_batch(
    translations_data: Dict[str, Dict[str, str]],
    batch_ids: List[str],
) -> str:
    """
    Build the `{text}` payload inserted into TRANSLATION_PROMPT for one batch.
    """
    context_sentences, context_translations = _collect_previous_context(
        translations_data, batch_ids
    )

    lines: List[str] = []

    if context_sentences or context_translations:
        lines.append("PREVIOUS CONTEXT (already translated; reference only)")
        if context_sentences:
            lines.append("Chinese Sentences:")
            lines.append(context_sentences)
            lines.append("")
        if context_translations:
            lines.append("English Translations:")
            lines.append(context_translations)
            lines.append("")
        lines.append("END OF CONTEXT")
        lines.append("")

    lines.append("CURRENT SENTENCES TO TRANSLATE:")

    for idx, sid in enumerate(batch_ids, start=1):
        source = translations_data[sid].get("source", "")
        lines.append(f"SENTENCE {idx}: {sid}")
        lines.append(source.strip())
        lines.append("")  # blank line between sentences

    future_context_src = _collect_future_context(translations_data, batch_ids)
    if future_context_src:
        lines.append("FUTURE CONTEXT (upcoming sentences; do not translate, for reference only)")
        lines.append(future_context_src)
        lines.append("")

    return "\n".join(lines).strip()


def _call_translation_api(
    batch_ids: List[str],
    translations_data: Dict[str, Dict[str, str]],
) -> Dict[str, str]:
    """
    Call the model for one batch of sentence ids.
    Returns a mapping {sent_id: translated_line}.
    """
    text_block = _build_text_block_for_batch(translations_data, batch_ids)
    prompt = TRANSLATION_PROMPT.format(text=text_block)
    system_content = SYSTEM_PROMPT

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

    # Parse provider and model from MODEL_NAME if possible
    # e.g. "openai:gpt-4o" -> provider="openai", model="gpt-4o"
    provider = None
    model = MODEL_NAME
    if ":" in MODEL_NAME:
        parts = MODEL_NAME.split(":", 1)
        if len(parts) == 2:
            provider, model = parts

    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ],
    }
    if provider:
        kwargs["provider"] = provider

    response = completion(**kwargs)

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
    sentences_path: Path,
    translations_path: Path,
) -> bool:
    """
    Translate all missing sentences in one chapter's translations file, but stop
    after the first batch so users can review before continuing.
    Returns True if a batch was processed.
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
        return False

    print(
        f"  Found {sum(len(b) for b in batches)} missing sentence(s) "
        f"in {len(batches)} batch(es)."
    )

    changed = False
    processed_batch = False

    try:
        for batch_idx, batch_ids in enumerate(batches, start=1):
            print(f"\n  Batch {batch_idx}/{len(batches)}: {len(batch_ids)} sentence(s)")
            try:
                batch_translations = _call_translation_api(
                    batch_ids, translations_data
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

            processed_batch = True
            print("  🚫 Single-batch mode active; rerun the script for the next batch.")
            break
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

    if processed_batch:
        print(f"\n  ✓ Completed one batch for {translations_path.name}")
    else:
        print("\n  ✓ No changes made for this chapter.")

    return processed_batch


def main() -> None:
    root = Path(__file__).resolve().parents[1]  # processor/ -> project root
    sentences_dir = (root / "renderer" / "public" / "sentences").resolve()
    translations_dir = (root / "renderer" / "public" / "translations").resolve()

    if not sentences_dir.exists():
        raise SystemExit(f"Sentences directory not found: {sentences_dir}")

    _setup_any_llm()
    chapter_pairs = _prepare_translation_files(sentences_dir, translations_dir)

    wanted: List[str] = []
    if len(sys.argv) > 1:
        wanted = list(sys.argv[1:])

    processed_any = False

    for sentences_path, translations_path in chapter_pairs:
        chapter_id = sentences_path.stem.split(".")[0]  # "c1"
        if wanted and chapter_id not in wanted:
            continue
        did_process = _translate_chapter(sentences_path, translations_path)
        if did_process:
            processed_any = True
            break

    if processed_any:
        print("\nSingle batch completed. Run again for the next batch.")
    else:
        print("\nAll done (no batches needed).")


if __name__ == "__main__":
    main()
