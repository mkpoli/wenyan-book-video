import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv
from any_llm import completion
import translate as base_translate


def load_missing_sentences(limit: int = 5) -> Tuple[List[str], List[str], Path, str, str, str]:
    """Collect source sentences that are missing translations.
    Returns (missing_sources, missing_sids, translations_path, previous_context, previous_translation, future_context).
    """
    # Determine project root and directories (same logic as translate.py)
    root = Path(__file__).resolve().parents[1]
    sentences_dir = (root / "renderer" / "public" / "sentences").resolve()
    translations_dir = (root / "renderer" / "public" / "translations").resolve()

    # Ensure translation files exist (same as translate.py's preparation)
    chapter_pairs = base_translate._prepare_translation_files(sentences_dir, translations_dir)
    
    missing_sids: List[str] = []
    missing_sources: List[str] = []
    
    # We'll just take the first chapter that has missing sentences for simplicity of context
    for _, translations_path in chapter_pairs:
        data = json.loads(translations_path.read_text(encoding="utf-8"))
        items = list(data.items())
        
        # Identify missing in this chapter
        chapter_missing_sids = []
        for sid, entry in items:
            if not entry.get("translation", "").strip():
                src = entry.get("source", "")
                if isinstance(src, str) and src:
                    chapter_missing_sids.append(sid)
                    if len(missing_sids) + len(chapter_missing_sids) >= limit:
                        break
        
        if chapter_missing_sids:
            # Let's use them (up to limit)
            needed = limit - len(missing_sids)
            subset = chapter_missing_sids[:needed]
            
            # Retrieve source text
            for sid in subset:
                missing_sources.append(data[sid]["source"])
            
            # Generate context using base_translate helpers
            # Previous context for the FIRST sentence in the batch
            prev_src, prev_trans = base_translate._collect_previous_context(data, [subset[0]])
            
            # Future context AFTER the LAST sentence in the batch
            # Note: base_translate._collect_future_context logic was updated in translate.py 
            # to collect context relevant to the batch (i.e. after the last ID).
            future_ctx = base_translate._collect_future_context(data, subset)
            
            return missing_sources, subset, translations_path, prev_src, prev_trans, future_ctx

    return [], [], Path("."), "", "", ""


def load_config():
    config_path = Path(__file__).resolve().parent / "translate.toml"
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    with config_path.open("rb") as f:
        cfg = tomllib.load(f)
    
    trans_cfg = cfg.get("translation", {})
    comp_cfg = cfg.get("comparison", {})
    eval_cfg = cfg.get("evaluation", {})
    
    system_prompt = trans_cfg.get("system_prompt")
    translation_prompt = trans_cfg.get("translation_prompt")
    models = comp_cfg.get("models", [])
    
    if not models:
        # Fallback to the single model if comparison list is empty
        m = trans_cfg.get("model_name")
        if m:
            models = [m]
        else:
            print("No models found in translate.toml")
            sys.exit(1)
        
    if not system_prompt or not translation_prompt:
        print("Missing system_prompt or translation_prompt in config")
        sys.exit(1)

    eval_model = eval_cfg.get("model", "deepseek:deepseek-chat")
    eval_prompt = eval_cfg.get("prompt", "")

    return models, system_prompt, translation_prompt, eval_model, eval_prompt

def build_prompt_text(input_lines: List[str], previous_context: str = "", previous_translation: str = "", future_context: str = "") -> str:
    lines = []
    
    if previous_context or previous_translation:
        lines.append("PREVIOUS CONTEXT (already translated; reference only)")
        if previous_context:
            lines.append("Chinese Sentences:")
            lines.append(previous_context)
            lines.append("")
        if previous_translation:
            lines.append("English Translations:")
            lines.append(previous_translation)
            lines.append("")
        lines.append("END OF CONTEXT")
        lines.append("")

    lines.append("CURRENT SENTENCES TO TRANSLATE:")
    for idx, line in enumerate(input_lines, start=1):
        lines.append(f"SENTENCE {idx}: test-s{idx}")
        lines.append(line.strip())
        lines.append("")

    if future_context:
        lines.append("FUTURE CONTEXT (upcoming sentences; do not translate, for reference only)")
        lines.append(future_context)
        lines.append("")
        
    return "\n".join(lines).strip()

def run_translation(model_name: str, system_prompt: str, user_prompt: str) -> List[str]:
    print(f"  Running {model_name}...")
    
    provider = None
    model = model_name
    if ":" in model_name:
        parts = model_name.split(":", 1)
        if len(parts) == 2:
            provider, model = parts
            
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if provider:
        kwargs["provider"] = provider

    try:
        response = completion(**kwargs)
        content = response.choices[0].message.content or ""
        
        # Try to parse JSON
        # Some models might wrap JSON in markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(content)
            translations = data.get("translations", [])
            results = []
            # We want to maintain order, assumes API returns in order or we can sort by ID
            # Our prompt asks for unique IDs: test-s1, test-s2...
            # Let's map ID to translation
            trans_map = {}
            for t in translations:
                if isinstance(t, dict):
                    tid = t.get("id")
                    tval = t.get("translation")
                    if tid and tval:
                        trans_map[tid] = tval
            
            # Reconstruct list in order
            # Maximum index we expect is implicit from caller, but here we don't know N.
            # We'll just sort by ID number.
            sorted_keys = sorted(trans_map.keys(), key=lambda x: int(x.split("-s")[1]) if "-s" in x else 0)
            for k in sorted_keys:
                results.append(trans_map[k])
                
            return results
        except json.JSONDecodeError:
            return [f"[JSON Parse Error] Raw: {content}"]
    except Exception as e:
        return [f"[Error] {e}"]

def run_evaluation(
    model_name: str,
    eval_template: str,
    source_lines: List[str],
    prev_context: str,
    future_context: str,
    model_translations: Dict[str, List[str]]
) -> Dict[str, Any]:
    print(f"\n  Running Evaluation (Judge: {model_name})...")
    
    # Flatten source lines for the prompt
    source_text = "\n".join(source_lines)
    
    # Anonymize candidates to avoid bias
    alias_map = {}
    candidates_str = ""
    start_char_code = 65 # 'A'
    
    # Sort for deterministic order
    sorted_models = sorted(model_translations.keys())
    
    for i, m_name in enumerate(sorted_models):
        alias = f"Candidate {chr(start_char_code + i)}"
        alias_map[alias] = m_name
        
        lines = model_translations[m_name]
        m_text = "\n".join(lines)
        candidates_str += f"### {alias}\n{m_text}\n\n"
        
    user_prompt = eval_template.format(
        source_segment=source_text,
        previous_context=prev_context,
        future_context=future_context,
        candidates=candidates_str.strip()
    )
    
    # Use a generic system prompt for the judge if not specified in the template (which it isn't usually, 
    # but the template itself acts as the main instruction. We'll pass a minimal system prompt or just rely on the user prompt if the template is full).
    # The config template I added is designed to be the USER prompt or SYSTEM prompt? 
    # In `run_translation`, we use a specific system prompt relative to translation.
    # For evaluation, the prompt I added in toml is quite instructive. Let's use it as the User prompt, 
    # and give a generic System prompt.
    
    system_inst = "You are an expert impartial judge of translation quality."
    
    provider = None
    model = model_name
    if ":" in model_name:
        parts = model_name.split(":", 1)
        if len(parts) == 2:
            provider, model = parts

    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_inst},
            {"role": "user", "content": user_prompt},
        ],
    }
    
    if provider:
        kwargs["provider"] = provider

    try:
        response = completion(**kwargs)
        content = response.choices[0].message.content or ""
        
        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        try:
            data = json.loads(content)
            
            # De-anonymize the best model
            best_alias = data.get("best_model", "")
            # Verify if it matches an alias
            real_best = best_alias
            for alias, real_name in alias_map.items():
                if alias in best_alias:
                    real_best = real_name
                    break
            
            data["best_model"] = real_best
            return data
        except json.JSONDecodeError:
            return {"error": "JSON Parse Error", "raw_output": content}
            
    except Exception as e:
        return {"error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Compare translations across models.")
    parser.add_argument("input_text", nargs="*", help="Lines of text to translate")
    parser.add_argument("--file", "-f", help="Read input lines from file")
    parser.add_argument("--list-models", nargs="?", const="all", default=None,
                        help="List available models. Optionally specify a provider name (e.g., 'anthropic').")
    parser.add_argument("--save", "-s", help="Path to save comparison results as JSON")
    parser.add_argument("--limit", "-n", type=int, default=5, help="Max number of missing sentences to load (default: 5)")
    
    args = parser.parse_args()
    load_dotenv()

    if args.list_models is not None:
        # Determine which providers to list
        provider_arg = args.list_models
        try:
            from any_llm.api import list_models
        except ImportError:
            from any_llm import list_models

        providers_to_check = []
        if provider_arg == "all":
            providers_to_check = ["openai", "anthropic", "gemini", "deepseek", "meta", "mistral"]
        else:
            providers_to_check = [provider_arg]

        print("Available models in any_llm (by provider):")
        for p in providers_to_check:
            try:
                models = list_models(p)
                if models:
                    print(f"\n[{p}]")
                    for m in models:
                        if hasattr(m, 'id'):
                            print(f" - {m.id}")
                        else:
                            print(f" - {m}")
                else:
                    print(f"\n[{p}] - No models found or empty list.")
            except Exception as ex:
                print(f"\n[{p}] - Error listing models: {ex}")
        return
    
    models, system_prompt, translation_template, eval_model, eval_prompt = load_config()
    
    input_lines = []
    input_sids = []
    translations_path = None
    previous_context = ""
    previous_translation = ""
    future_context = ""

    if args.file:
        path = Path(args.file)
        if path.exists():
            input_lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif args.input_text:
        input_lines = args.input_text
    else:
        # Automatically load sentences that need translation from the translate pipeline
        input_lines, input_sids, translations_path, previous_context, previous_translation, future_context = load_missing_sentences(limit=args.limit)
        if not input_lines:
            print("No input provided and no missing sentences found. Exiting.")
            return


    if not input_lines:
        print("No input text found.")
        return

    text_block = build_prompt_text(input_lines, previous_context, previous_translation, future_context)
    user_prompt = translation_template.format(text=text_block)

    print(f"Comparing {len(models)} models on {len(input_lines)} sentences...")
    
    # Preview source paragraph
    paragraph_preview = "".join(input_lines)
    print("\n" + "="*80)
    print("SOURCE PARAGRAPH PREVIEW")
    print("="*80)
    print(paragraph_preview)
    print("="*80 + "\n")
    
    results = {
        "_meta": {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
    }
    
    for model in models:
        trans_lines = run_translation(model, system_prompt, user_prompt)
        results[model] = trans_lines

        # Save results individually as we go
        if getattr(args, "save", None):
            out_path = Path(args.save)
            if out_path.suffix.lower() == ".json":
                out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                # Save as Markdown
                lines = []
                lines.append(f"# Translation Comparison Report")
                lines.append("")
                lines.append("## System Prompt")
                lines.append("```")
                lines.append(results["_meta"]["system_prompt"])
                lines.append("```")
                lines.append("")
                lines.append("## User Prompt")
                lines.append("```")
                lines.append(results["_meta"]["user_prompt"])
                lines.append("```")
                lines.append("")
                lines.append("## Comparison")
                
                for i, src in enumerate(input_lines):
                    lines.append(f"### Sentence {i+1}")
                    lines.append(f"**Source**: {src}")
                    lines.append("")
                    for m in models:
                         t_list = results.get(m, [])
                         val = t_list[i] if i < len(t_list) else "<missing>"
                         lines.append(f"- **{m}**: {val}")
                    lines.append("")
                    lines.append("---")
                    lines.append("")
                
                out_path.write_text("\n".join(lines), encoding="utf-8")

            print(f"  💾 Saved partial progress to {out_path}")

    # Run Evaluation if we have results
    eval_result = {}
    if eval_prompt and eval_model:
        # Collect translations for evaluation
        # We need a dict of {model: [lines]} which is exactly what `results` is (minus _meta)
        eval_candidates = {k: v for k, v in results.items() if k != "_meta"}
        
        eval_result = run_evaluation(
            eval_model,
            eval_prompt,
            input_lines,
            previous_context,
            future_context,
            eval_candidates
        )
        results["_evaluation"] = eval_result

        # Save refined translation as a distinct model entry for comparison
        refined = eval_result.get("better_translation")
        if refined and isinstance(refined, str):
            # Split into lines. The prompt asks for 1:1 mapping with newlines.
            refined_lines = [line.strip() for line in refined.strip().split('\n')]
            results["judge:refined"] = refined_lines
            if "judge:refined" not in models:
                models.append("judge:refined")
        
        # Save refined translation to actual translations file if available
        if translations_path and input_sids and refined:
            # We need to map refined lines back to IDs
            # refined_lines has same length as input_sids ideally
            if len(refined_lines) == len(input_sids):
                # Load current data
                import json
                try:
                    data = json.loads(translations_path.read_text(encoding="utf-8"))
                    for i, sid in enumerate(input_sids):
                        if sid in data:
                            data[sid]["translation"] = refined_lines[i]
                            
                            # Add candidates map only if they differ
                            # Collect candidates for this sentence index i
                            cands = {}
                            distinct_values = set()
                            
                            for m in results:
                                if m.startswith("_") or m == "judge:refined":
                                    continue
                                t_list = results[m]
                                if i < len(t_list):
                                    val = t_list[i]
                                    cands[m] = val
                                    distinct_values.add(val)
                            
                            # Only save candidates if there is more than 1 distinct translation
                            # (considering the refined one is the final one, let's just store the other models as history)
                            if len(distinct_values) > 1:
                                data[sid]["candidates"] = cands

                    # Write back
                    translations_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    print(f"  💾 Saved refined translations to {translations_path}")
                except Exception as e:
                    print(f"  ⚠️ Could not save to translations file: {e}")
            else:
                print(f"  ⚠️ Refined line count ({len(refined_lines)}) mismatch with input sentences ({len(input_sids)}). Not saving to file.")

        # Final Save with evaluation
        if getattr(args, "save", None):
            out_path = Path(args.save)
            if out_path.suffix.lower() == ".json":
                out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                # Generate Markdown Report (Full)
                lines = []
                lines.append(f"# Translation Comparison Report")
                lines.append("")
                lines.append("## System Prompt")
                lines.append("```")
                lines.append(results["_meta"]["system_prompt"])
                lines.append("```")
                lines.append("")
                lines.append("## User Prompt")
                lines.append("```")
                lines.append(results["_meta"]["user_prompt"])
                lines.append("```")
                lines.append("")
                
                lines.append("## Comparison")
                for i, src in enumerate(input_lines):
                    lines.append(f"### Sentence {i+1}")
                    lines.append(f"**Source**: {src}")
                    lines.append("")
                    for m in models:
                            t_list = results.get(m, [])
                            val = t_list[i] if i < len(t_list) else "<missing>"
                            lines.append(f"- **{m}**: {val}")
                    lines.append("")
                    lines.append("---")
                    lines.append("")
                
                if "_evaluation" in results and results["_evaluation"]:
                    ev = results["_evaluation"]
                    lines.append("## Evaluation (Judge: " + eval_model + ")")
                    if "error" in ev:
                        lines.append(f"**Error**: {ev['error']}")
                    else:
                        lines.append(f"**Best Model**: {ev.get('best_model', 'N/A')}")
                        lines.append("")
                        lines.append(f"**Reasoning**: {ev.get('reasoning', 'N/A')}")
                        lines.append("")
                        lines.append(f"**Best/Improved Translation**:")
                        lines.append(f"> {ev.get('better_translation', 'N/A')}")
                    lines.append("")
                
                out_path.write_text("\n".join(lines), encoding="utf-8")
                print(f"  💾 Saved complete report to {out_path}")
    print("\n" + "─"*80)
    print("📊 COMPARISON RESULTS")
    print("─"*80)
    
    # Calculate max model name length for padding
    max_len = max(len(m) for m in models)
    
    for i, original in enumerate(input_lines):
        print(f"\n[Source] {original}")
        for model in models:
            t_list = results[model]
            # Try to match by index, but handle errors/mismatches
            val = t_list[i] if i < len(t_list) else "<missing/error>"
            print(f"  {model:<{max_len}} | {val}")
            
    if "_evaluation" in results and results["_evaluation"]:
        ev = results["_evaluation"]
        print("\n" + "─"*80)
        print(f"🏆 EVALUATION (Judge: {eval_model})")
        print("─"*80)
        if "error" in ev:
             print(f"Error: {ev['error']}")
        else:
            print(f"Best Model: {ev.get('best_model')}")
            print(f"Reasoning:  {ev.get('reasoning')}")
            print(f"Better Tx:  {ev.get('better_translation')}")

if __name__ == "__main__":
    main()
