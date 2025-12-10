import json
import os
import sys
import argparse
import tomllib
from pathlib import Path
from typing import Dict, List, Tuple, Any

from dotenv import load_dotenv
from any_llm import completion

# Import translate.py logic is effectively rewriting it, but we can reuse some helper structures if we want.
# Actually, since we are REPLACING translate.py's main logic with the merged one, we will just rewrite translate.py.
# But "translate-compare.py" has dependency on "translate.py" for helper functions? 
# "import translate as base_translate" <-- Yes it does.
# So we need to be careful. Ideally `translate.py` is self-contained.
# I will copy the helper functions into the new translate.py if they are good, or keep them.
# The `_build_batches_for_chapter` etc in translate.py are solid.

def load_config():
    """
    Load translation configuration from translate.toml.
    Returns (models, system_prompt, translation_prompt, eval_model, eval_prompt) tuple.
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
    except Exception as exc:
        raise ValueError(
            f"Failed to parse translation config {config_path}: {exc}"
        ) from exc

    trans_cfg = cfg.get("translation", {})
    eval_cfg = cfg.get("evaluation", {})

    models = trans_cfg.get("models")
    if not models or not isinstance(models, list):
         # Fallback or Error? Plan said "no legacy support".
         # But maybe user hasn't updated toml yet? We just updated it.
         # If missing, error out.
         raise ValueError(
            f"Config file {config_path} must have 'models' list in [translation] section"
         )

    system_prompt = trans_cfg.get("system_prompt")
    translation_prompt = trans_cfg.get("translation_prompt")
    
    if not isinstance(translation_prompt, str):
        raise ValueError(f"Missing 'translation_prompt' string in [translation]")
    if not isinstance(system_prompt, str):
        raise ValueError(f"Missing 'system_prompt' string in [translation]")
        
    eval_model = eval_cfg.get("model", "deepseek:deepseek-chat")
    eval_prompt = eval_cfg.get("prompt", "")

    return models, system_prompt, translation_prompt, eval_model, eval_prompt


MODEL_NAMES, SYSTEM_PROMPT, TRANSLATION_PROMPT, EVAL_MODEL, EVAL_PROMPT = load_config()

API_DELAY_SECONDS = 1.0
MAX_SENTENCES_PER_BATCH = 5 # Reduced for multi-model safety? Or keep 30?
# translate-compare used limit=5 default.
# translate.py used 30.
# With multiple models and judge, 30 might be too slow/expensive per batch?
# Let's stick closer to translate.py's batch logic but maybe lower text limit slightly?
# Actually, for correctness, smaller batches (5-10) are better for the Judge context window too.
MAX_SENTENCES_PER_BATCH = 5 
MAX_CHARS_PER_BATCH = 2000
MAX_CONTEXT_CHARS = 1800
MAX_FUTURE_CONTEXT_CHARS = 500


def _sort_chapter_sentences_file(path: Path) -> int:
    name = path.stem.split(".")[0]
    num_str = name.lstrip("c")
    return int(num_str) if num_str.isdigit() else 0

def _sentence_sort_key(sent_id: str) -> int:
    if "-s" in sent_id:
        try:
            return int(sent_id.split("-s", 1)[1])
        except ValueError:
            return 0
    return 0

def _setup_any_llm() -> None:
    load_dotenv()

def _prepare_translation_files(sentences_dir: Path, translations_dir: Path) -> List[Tuple[Path, Path]]:
    translations_dir.mkdir(exist_ok=True, parents=True)
    chapter_pairs: List[Tuple[Path, Path]] = []
    
    for sentences_path in sorted(sentences_dir.glob("c*.sentences.json"), key=_sort_chapter_sentences_file):
        chapter_id = sentences_path.stem.split(".")[0]
        translations_path = translations_dir / f"{chapter_id}.translations.json"
        
        if not translations_path.exists():
            canon = json.loads(sentences_path.read_text(encoding="utf-8"))
            init_data: Dict[str, Dict[str, str]] = {}
            for s in canon.get("sentences", []):
                sid = s.get("id")
                src = s.get("source", "")
                if sid and src:
                    init_data[sid] = {"source": src, "translation": ""}
            translations_path.write_text(json.dumps(init_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Created {translations_path}")
            
        chapter_pairs.append((sentences_path, translations_path))
    print(f"Prepared {len(chapter_pairs)} sentence translation files")
    return chapter_pairs

def _build_batches_for_chapter(translations_data: Dict[str, Dict[str, str]]) -> List[List[str]]:
    missing_ids = [
        sid for sid in sorted(translations_data.keys(), key=_sentence_sort_key)
        if not translations_data.get(sid, {}).get("translation", "").strip()
    ]
    batches = []
    current = []
    current_chars = 0
    for sid in missing_ids:
        source = translations_data[sid].get("source", "")
        length = len(source)
        if current and (len(current) >= MAX_SENTENCES_PER_BATCH or current_chars + length > MAX_CHARS_PER_BATCH):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(sid)
        current_chars += length
    if current:
        batches.append(current)
    return batches

def _collect_previous_context(translations_data: Dict[str, Dict[str, str]], batch_ids: List[str], max_chars: int = MAX_CONTEXT_CHARS) -> Tuple[str, str]:
    if not batch_ids: return "", ""
    ordered_ids = sorted(translations_data.keys(), key=_sentence_sort_key)
    try:
        first_idx = ordered_ids.index(batch_ids[0])
    except ValueError:
        return "", ""
        
    context_ids = ordered_ids[:first_idx]
    collected = []
    running_chars = 0
    for sid in reversed(context_ids):
        entry = translations_data.get(sid) or {}
        src = (entry.get("source") or "").strip()
        trans = (entry.get("translation") or "").strip()
        if not src and not trans: continue
        add = len(src) + len(trans)
        if add == 0: continue
        if running_chars + add > max_chars: break
        collected.append((src, trans))
        running_chars += add
        
    if not collected: return "", ""
    collected.reverse()
    return " ".join(s for s, _ in collected if s).strip(), " ".join(t for _, t in collected if t).strip()

def _collect_future_context(translations_data: Dict[str, Dict[str, str]], batch_ids: List[str], max_chars: int = MAX_FUTURE_CONTEXT_CHARS) -> str:
    if not batch_ids: return ""
    ordered_ids = sorted(translations_data.keys(), key=_sentence_sort_key)
    try:
        last_idx = ordered_ids.index(batch_ids[-1])
    except ValueError:
        return ""
    context_ids = ordered_ids[last_idx+1:]
    collected = []
    running_chars = 0
    for sid in context_ids:
        entry = translations_data.get(sid) or {}
        src = (entry.get("source") or "").strip()
        if not src: continue
        if running_chars + len(src) > max_chars: break
        collected.append(src)
        running_chars += len(src)
    return " ".join(collected).strip()

def _build_text_block_for_batch(translations_data: Dict[str, Dict[str, str]], batch_ids: List[str]) -> str:
    # This builds the text block for the TRANSLATION PROMPT
    ctx_src, ctx_trans = _collect_previous_context(translations_data, batch_ids)
    lines = []
    if ctx_src or ctx_trans:
        lines.append("PREVIOUS CONTEXT (already translated; reference only)")
        if ctx_src:
            lines.append("Chinese Sentences:"); lines.append(ctx_src); lines.append("")
        if ctx_trans:
            lines.append("English Translations:"); lines.append(ctx_trans); lines.append("")
        lines.append("END OF CONTEXT"); lines.append("")
    
    lines.append("CURRENT SENTENCES TO TRANSLATE:")
    for idx, sid in enumerate(batch_ids, start=1):
        source = translations_data[sid].get("source", "")
        # Use simple ID or real ID? Prompt says "id": "..."
        # We'll include the real ID in the prompt so the model returns it back if it's JSON
        lines.append(f"SENTENCE {idx}: {sid}")
        lines.append(source.strip())
        lines.append("")
        
    fut = _collect_future_context(translations_data, batch_ids)
    if fut:
        lines.append("FUTURE CONTEXT (upcoming sentences; do not translate, for reference only)")
        lines.append(fut)
        lines.append("")
    return "\n".join(lines).strip()

def _call_translation_api_single_model(model_name: str, text_block: str) -> Dict[str, str]:
    prompt = TRANSLATION_PROMPT.format(text=text_block)
    
    provider = None
    model = model_name
    if ":" in model_name:
        parts = model_name.split(":", 1)
        if len(parts) == 2:
            provider, model = parts
            
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    if provider: kwargs["provider"] = provider
    
    print(f"    Running {model_name}...")
    try:
        response = completion(**kwargs)
        raw = (response.choices[0].message.content or "").strip()
        
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
            
        payload = json.loads(raw)
        t_list = payload.get("translations", [])
        if not isinstance(t_list, list): return {}
        
        result = {}
        for entry in t_list:
            if isinstance(entry, dict):
                sid = entry.get("id")
                val = entry.get("translation")
                if sid and val:
                    result[sid] = val.strip()
        return result
    except Exception as e:
        print(f"    ❌ Error with {model_name}: {e}")
        return {}

def run_evaluation(
    source_lines: List[str],
    prev_context: str,
    future_context: str,
    model_translations: Dict[str, List[str]]
) -> Dict[str, Any]:
    print(f"    Running Evaluation (Judge: {EVAL_MODEL})...")
    
    # 1. Prepare source lines [1] ...
    source_text_list = []
    for i, line in enumerate(source_lines, start=1):
         trimmed = line.strip()
         source_text_list.append(f"[{i}] {trimmed}")
    source_text = "\n".join(source_text_list)
    
    # 2. Anonymize
    alias_map = {}
    candidates_str = ""
    start_char_code = 65 
    sorted_models = sorted(model_translations.keys())
    
    for i, m_name in enumerate(sorted_models):
        alias = f"Candidate {chr(start_char_code + i)}"
        alias_map[alias] = m_name
        lines = model_translations[m_name]
        m_text = "\n".join(lines)
        candidates_str += f"### {alias}\n{m_text}\n\n"
        
    user_prompt = EVAL_PROMPT.format(
        source_segment=source_text,
        previous_context=prev_context,
        future_context=future_context,
        candidates=candidates_str.strip()
    )
    
    sys_inst = "You are an expert impartial judge of translation quality."
    
    provider = None
    model = EVAL_MODEL
    if ":" in EVAL_MODEL:
        parts = EVAL_MODEL.split(":", 1)
        if len(parts) == 2:
            provider, model = parts
            
    try:
        kwargs = {"model": model, "messages": [{"role": "system", "content": sys_inst}, {"role": "user", "content": user_prompt}]}
        if provider: kwargs["provider"] = provider
        
        # print("DEBUG: Eval Prompt:\n", user_prompt)
        
        response = completion(**kwargs)
        content = response.choices[0].message.content or ""
        
        # 3. Parse Custom Output
        result = {}
        lines = content.splitlines()
        current_section = None
        refined_lines_map = {}
        
        import re
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            if line.lower().startswith("best model:"):
                val = line.split(":", 1)[1].strip().replace("*", "")
                # De-anonymize
                for alias, real_name in alias_map.items():
                    if alias in val:
                        val = real_name
                        break
                result["best_model"] = val
            elif line.lower().startswith("reasoning:"):
                result["reasoning"] = line.split(":", 1)[1].strip()
            elif "refined translation" in line.lower() or "better translation" in line.lower():
                current_section = "refined"
            elif current_section == "refined":
                m = re.match(r"^\[(\d+)\](.*)", line)
                if m:
                    idx = int(m.group(1))
                    text = m.group(2).strip()
                    refined_lines_map[idx] = text
                    
        # Reconstruct list
        if refined_lines_map:
            final_list = []
            for i in range(1, len(source_lines) + 1):
                final_list.append(refined_lines_map.get(i, ""))
            result["better_translation"] = final_list
            
        return result
    except Exception as e:
        return {"error": str(e)}

def _translate_chapter_batch(
    translations_path: Path, 
    translations_data: Dict[str, Dict[str, str]], 
    batch_ids: List[str]
) -> bool:
    
    # 1. Gather Context for this batch
    prev_src, prev_trans = _collect_previous_context(translations_data, batch_ids)
    fut_src = _collect_future_context(translations_data, batch_ids)
    
    source_lines = [translations_data[sid]["source"] for sid in batch_ids]
    
    # Preview source paragraph
    paragraph_preview = "".join(source_lines)
    print("\n" + "="*80)
    print("SOURCE PARAGRAPH PREVIEW")
    print("="*80)
    print(paragraph_preview)
    print("="*80 + "\n")
    
    text_block = _build_text_block_for_batch(translations_data, batch_ids)
    
    # 2. Run all models
    model_results: Dict[str, Dict[str, str]] = {} # model -> {sid -> text}
    
    print(f"  🤖 Translating batch with {len(MODEL_NAMES)} models...")
    for model in MODEL_NAMES:
        res = _call_translation_api_single_model(model, text_block)
        model_results[model] = res
        
    # 3. Prepare for Evaluation
    # We need {model_name: [line1, line2...]} corresponding to batch_ids order
    eval_candidates: Dict[str, List[str]] = {}
    
    for model in MODEL_NAMES:
        res = model_results.get(model, {})
        lines = []
        for sid in batch_ids:
            lines.append(res.get(sid, "<missing>"))
        eval_candidates[model] = lines
        
    # 4. Run Evaluation
    eval_res = run_evaluation(source_lines, prev_src, fut_src, eval_candidates)
    
    refined_list = eval_res.get("better_translation")
    best_model = eval_res.get("best_model")
    
    # 5. Determine Final Translation and Candidates
    # If refined exist and matches length, use it. Else fallback to best model, else first model.
    
    final_translations = []
    
    if refined_list and len(refined_list) == len(batch_ids):
        final_translations = refined_list
    else:
        # Fallback
        fallback_model = best_model if (best_model and best_model in model_results) else MODEL_NAMES[0]
        print(f"    ⚠️ Refined translation missing or mismatch. Fallback to {fallback_model}")
        res = model_results.get(fallback_model, {})
        for sid in batch_ids:
            final_translations.append(res.get(sid, ""))
            
    # 6. Save to Data
    changed = False
    
    # Also prepare for printing table
    print("\n" + "─"*80)
    print(f"Batch Result (Judge: {best_model or 'N/A'})")
    print("─"*80)
    
    for i, sid in enumerate(batch_ids):
        entry = translations_data.get(sid) or {}
        
        # Refined
        refined_text = final_translations[i]
        entry["translation"] = refined_text
        
        print(f"\n[Source] {source_lines[i]}")
        print(f"  {'Refined (Judge)':<25} | {refined_text}")

        # Candidates
        cands = {}
        distinct_vals = set()
        
        for model in MODEL_NAMES:
            t_list = eval_candidates.get(model, [])
            if i < len(t_list):
                val = t_list[i]
                cands[model] = val
                distinct_vals.add(val)
                print(f"  {model:<25} | {val}")
        
        if len(distinct_vals) > 1:
            entry["candidates"] = cands
        
        translations_data[sid] = entry
        changed = True

    # 7. Write File
    if changed:
        translations_path.write_text(json.dumps(translations_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  💾 Saved batch to {translations_path.name}")
        
    return True


def _translate_chapter(sentences_path: Path, translations_path: Path) -> bool:
    print("\n" + "=" * 80)
    print(f"Translating sentence file: {sentences_path.stem}")
    print("=" * 80)

    translations_data = json.loads(translations_path.read_text(encoding="utf-8"))
    batches = _build_batches_for_chapter(translations_data)

    if not batches:
        print("  ✓ No missing translations.")
        return False

    print(f"  Found {sum(len(b) for b in batches)} missing sentence(s) in {len(batches)} batch(es).")
    
    # Process only ONE batch per run as per original design for safety/review
    batch = batches[0]
    print(f"  Processing Batch 1/{len(batches)}: {len(batch)} sentences")
    
    try:
        _translate_chapter_batch(translations_path, translations_data, batch)
    except KeyboardInterrupt:
        print("\n  ↯ Interrupted.")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
        
    print("  🚫 Single-batch mode active; rerun for next.")
    return True

def main():
    root = Path(__file__).resolve().parents[1]
    sentences_dir = (root / "renderer" / "public" / "sentences").resolve()
    translations_dir = (root / "renderer" / "public" / "translations").resolve()

    if not sentences_dir.exists():
        raise SystemExit(f"Sentences directory not found: {sentences_dir}")

    _setup_any_llm()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--chapter", help="Specific chapter ID (e.g. '9' or 'c9')")
    parser.add_argument("--limit", type=int, default=1, help="Limit number of batches (default 1 implicit)") # Actually logic limits to 1 batch anyway
    args = parser.parse_args()
    
    wanted_chapter = None
    if args.chapter:
        wanted_chapter = args.chapter if args.chapter.startswith("c") else f"c{args.chapter}"

    chapter_pairs = _prepare_translation_files(sentences_dir, translations_dir)
    processed_any = False

    for sentences_path, translations_path in chapter_pairs:
        cid = sentences_path.stem.split(".")[0]
        if wanted_chapter and cid != wanted_chapter:
            continue
            
        if _translate_chapter(sentences_path, translations_path):
            processed_any = True
            break # Stop after one chapter is processed (one batch of one chapter)

    if processed_any:
        print("\nDone.")
    else:
        print("\nNothing processed.")

if __name__ == "__main__":
    main()
