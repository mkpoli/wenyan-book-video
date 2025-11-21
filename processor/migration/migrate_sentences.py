from __future__ import annotations

import json
import shutil
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import importlib.util
import re

# Add parent directory to sys.path to import sibling modules
sys.path.append(str(Path(__file__).parent.parent))

# Import build-sentences.py dynamically because of the hyphen
build_sentences_path = Path(__file__).parent.parent / "build-sentences.py"
spec = importlib.util.spec_from_file_location("build_sentences", build_sentences_path)
build_sentences_module = importlib.util.module_from_spec(spec)
sys.modules["build_sentences"] = build_sentences_module
spec.loader.exec_module(build_sentences_module)

build_sentences_for_chapter = build_sentences_module.build_sentences_for_chapter


def normalize_text(text: str) -> str:
    """Normalize text for comparison (ignore whitespace differences)."""
    return "".join(text.split())


def count_han_chars(text: str) -> int:
    """Count characters in Unicode Han range."""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def split_transcript_data(
    original_ipa: str, original_tupa: str, new_segments: List[str]
) -> List[Dict[str, str]]:
    """
    Split IPA and Tupa strings corresponding to new segments.
    """
    segment_char_counts = [count_han_chars(s) for s in new_segments]
    total_chars = sum(segment_char_counts)

    if total_chars == 0:
        return [{"ipa": "", "tupa": ""} for _ in new_segments]

    ipa_tokens = original_ipa.split()
    tupa_tokens = original_tupa.split()

    ipa_results = []
    tupa_results = []

    ipa_idx = 0
    tupa_idx = 0

    ipa_len = len(ipa_tokens)
    tupa_len = len(tupa_tokens)

    punctuation = [".", ",", "!", "?", "。", "，", "！", "？"]

    for i, count in enumerate(segment_char_counts):
        current_ipa = []
        current_tupa = []

        syllables_grabbed = 0
        while syllables_grabbed < count and ipa_idx < ipa_len:
            token = ipa_tokens[ipa_idx]
            if token in punctuation:
                current_ipa.append(token)
                ipa_idx += 1
                continue

            current_ipa.append(token)
            ipa_idx += 1
            syllables_grabbed += 1

        while ipa_idx < ipa_len and ipa_tokens[ipa_idx] in punctuation:
            current_ipa.append(ipa_tokens[ipa_idx])
            ipa_idx += 1

        syllables_grabbed = 0
        while syllables_grabbed < count and tupa_idx < tupa_len:
            token = tupa_tokens[tupa_idx]
            if token in punctuation:
                current_tupa.append(token)
                tupa_idx += 1
                continue

            current_tupa.append(token)
            tupa_idx += 1
            syllables_grabbed += 1

        while tupa_idx < tupa_len and tupa_tokens[tupa_idx] in punctuation:
            current_tupa.append(tupa_tokens[tupa_idx])
            tupa_idx += 1

        ipa_results.append(" ".join(current_ipa))
        tupa_results.append(" ".join(current_tupa))

    if ipa_idx < ipa_len and ipa_results:
        ipa_results[-1] += " " + " ".join(ipa_tokens[ipa_idx:])
    if tupa_idx < tupa_len and tupa_results:
        tupa_results[-1] += " " + " ".join(tupa_tokens[tupa_idx:])

    for i in range(len(ipa_results) - 1):
        if i + 1 < len(new_segments) and new_segments[i + 1].startswith("\n"):
            if ipa_results[i] and not ipa_results[i].rstrip().endswith("."):
                ipa_results[i] = ipa_results[i].rstrip() + " ."
            if tupa_results[i] and not tupa_results[i].rstrip().endswith("."):
                tupa_results[i] = tupa_results[i].rstrip() + " ."

    results = [
        {"ipa": ipa, "tupa": tupa} for ipa, tupa in zip(ipa_results, tupa_results)
    ]
    return results


def merge_transcripts(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not entries:
        return {}

    first = entries[0]
    if len(entries) == 1:
        return first.copy()

    merged_ipa = " ".join(e.get("ipa", "") for e in entries).strip()
    merged_tupa = " ".join(e.get("tupa", "") for e in entries).strip()

    merged_choices = []
    current_offset = 0
    full_source = ""

    for e in entries:
        source_len = len(e.get("source", ""))
        choices = e.get("choices", [])
        if choices:
            for c in choices:
                new_c = c.copy()
                if "indexInSource" in new_c:
                    new_c["indexInSource"] += current_offset
                merged_choices.append(new_c)
        
        full_source += e.get("source", "")
        current_offset += source_len

    result = {
        "source": full_source,
        "ipa": merged_ipa,
        "tupa": merged_tupa,
    }
    if merged_choices:
        result["choices"] = merged_choices

    return result


def merge_translations(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not entries:
        return {}

    first = entries[0]
    if len(entries) == 1:
        return first.copy()

    full_source = "".join(e.get("source", "") for e in entries)
    merged_translation = " ".join(e.get("translation", "") for e in entries).strip()

    return {
        "source": full_source,
        "translation": merged_translation
    }


def run_prettier(file_paths: List[Path]) -> None:
    if not file_paths:
        return
    
    print(f"Running prettier on {len(file_paths)} files...")
    try:
        cmd = ["npx", "prettier", "--write"] + [str(p) for p in file_paths]
        subprocess.run(cmd, check=True, capture_output=True)
        print("Prettier completed.")
    except subprocess.CalledProcessError as e:
        print(f"Prettier failed: {e}")
        print(f"Stderr: {e.stderr.decode()}")
    except FileNotFoundError:
        print("Prettier not found (npx not in path?), skipping.")


def migrate_chapter(
    chapter_num: int,
    chapters_dir: Path,
    sentences_dir: Path,
    translations_dir: Path,
    transcripts_dir: Path,
    segments_dir: Path,
) -> None:
    chapter_id = f"c{chapter_num}"
    print(f"Migrating {chapter_id}...")

    chapter_json_path = chapters_dir / f"{chapter_id}.json"
    
    old_transcripts_path = transcripts_dir / f"{chapter_id}.transcripts.json"
    if not old_transcripts_path.exists():
        print(f"  No transcripts found for {chapter_id}, skipping.")
        return

    with old_transcripts_path.open("r", encoding="utf-8") as f:
        old_transcripts_map = json.load(f)

    def get_id_num(key: str) -> int:
        try:
            return int(key.split("-s")[-1])
        except ValueError:
            return 0

    sorted_old_ids = sorted(old_transcripts_map.keys(), key=get_id_num)
    old_sentences_list = []
    for sid in sorted_old_ids:
        data = old_transcripts_map[sid]
        old_sentences_list.append({
            "id": sid,
            "source": data.get("source", ""),
            "data": data
        })

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_sentences_for_chapter(chapter_json_path, temp_path)
        
        new_sentences_path = temp_path / f"{chapter_id}.sentences.json"
        with new_sentences_path.open("r", encoding="utf-8") as f:
            new_data = json.load(f)
        new_sentences_list = new_data["sentences"]

    new_to_data_map: Dict[str, Dict[str, Any]] = {}
    new_to_old_ids_map: Dict[str, List[str]] = {}
    
    old_idx = 0
    new_idx = 0
    
    while new_idx < len(new_sentences_list):
        new_s = new_sentences_list[new_idx]
        new_source_norm = normalize_text(new_s["source"])
        
        if old_idx >= len(old_sentences_list):
            # Fallback: Add placeholder
            new_to_data_map[new_s["id"]] = {
                "source": new_s["source"],
                "ipa": "",
                "tupa": ""
            }
            new_idx += 1
            continue

        old_s = old_sentences_list[old_idx]
        old_source_norm = normalize_text(old_s["source"])

        if new_source_norm == old_source_norm:
            new_to_data_map[new_s["id"]] = old_s["data"]
            new_to_old_ids_map[new_s["id"]] = [old_s["id"]]
            old_idx += 1
            new_idx += 1
            continue

        if new_source_norm.startswith(old_source_norm):
            accumulated_old = [old_s]
            accumulated_text = old_source_norm
            
            curr_old_idx = old_idx + 1
            match_found = False
            
            while curr_old_idx < len(old_sentences_list):
                next_old = old_sentences_list[curr_old_idx]
                next_norm = normalize_text(next_old["source"])
                accumulated_old.append(next_old)
                accumulated_text += next_norm
                
                if accumulated_text == new_source_norm:
                    match_found = True
                    break
                
                if len(accumulated_text) > len(new_source_norm):
                    break
                
                curr_old_idx += 1
            
            if match_found:
                merged_data = merge_transcripts([o["data"] for o in accumulated_old])
                merged_data["source"] = new_s["source"]
                new_to_data_map[new_s["id"]] = merged_data
                new_to_old_ids_map[new_s["id"]] = [o["id"] for o in accumulated_old]
                old_idx = curr_old_idx + 1
                new_idx += 1
                continue

        if old_source_norm.startswith(new_source_norm):
            accumulated_new = [new_s]
            accumulated_text = new_source_norm
            
            curr_new_idx = new_idx + 1
            match_found = False
            
            while curr_new_idx < len(new_sentences_list):
                next_new = new_sentences_list[curr_new_idx]
                next_norm = normalize_text(next_new["source"])
                accumulated_new.append(next_new)
                accumulated_text += next_norm
                
                if accumulated_text == old_source_norm:
                    match_found = True
                    break
                
                if len(accumulated_text) > len(old_source_norm):
                    break
                
                curr_new_idx += 1
            
            if match_found:
                old_ipa = old_s["data"].get("ipa", "")
                old_tupa = old_s["data"].get("tupa", "")
                new_segments_sources = [ns["source"] for ns in accumulated_new]
                
                split_results = split_transcript_data(old_ipa, old_tupa, new_segments_sources)
                
                for i, ns in enumerate(accumulated_new):
                    split_data = split_results[i]
                    new_entry = {
                        "source": ns["source"],
                        "ipa": split_data["ipa"],
                        "tupa": split_data["tupa"]
                    }
                    new_to_data_map[ns["id"]] = new_entry
                    new_to_old_ids_map[ns["id"]] = [old_s["id"]]
                
                old_idx += 1
                new_idx = curr_new_idx + 1
                continue

        # Fallback: Add placeholder
        new_to_data_map[new_s["id"]] = {
            "source": new_s["source"],
            "ipa": "",
            "tupa": ""
        }
        new_idx += 1

    modified_files = []

    new_transcripts_map = {}
    for new_s in new_sentences_list:
        nid = new_s["id"]
        if nid in new_to_data_map:
            new_transcripts_map[nid] = new_to_data_map[nid]
    
    with old_transcripts_path.open("w", encoding="utf-8") as f:
        json.dump(new_transcripts_map, f, ensure_ascii=False, indent=2)
    modified_files.append(old_transcripts_path)

    old_translations_path = translations_dir / f"{chapter_id}.translations.json"
    if old_translations_path.exists():
        with old_translations_path.open("r", encoding="utf-8") as f:
            old_translations_map = json.load(f)
        
        new_translations_map = {}
        used_old_ids_for_translation = set()

        for new_s in new_sentences_list:
            nid = new_s["id"]
            if nid in new_to_old_ids_map:
                old_ids = new_to_old_ids_map[nid]
                old_entries = []
                for oid in old_ids:
                    if oid in old_translations_map:
                        old_entries.append(old_translations_map[oid])
                
                if old_entries:
                    if len(old_ids) == 1:
                        oid = old_ids[0]
                        if oid in used_old_ids_for_translation:
                             new_translations_map[nid] = {
                                 "source": new_s["source"],
                                 "translation": ""
                             }
                        else:
                             merged_entry = merge_translations(old_entries)
                             merged_entry["source"] = new_s["source"]
                             new_translations_map[nid] = merged_entry
                             used_old_ids_for_translation.add(oid)
                    else:
                        merged_entry = merge_translations(old_entries)
                        merged_entry["source"] = new_s["source"]
                        new_translations_map[nid] = merged_entry
                        for oid in old_ids:
                            used_old_ids_for_translation.add(oid)

            elif nid in new_to_data_map:
                 new_translations_map[nid] = {
                     "source": new_s["source"],
                     "translation": ""
                 }

        with old_translations_path.open("w", encoding="utf-8") as f:
            json.dump(new_translations_map, f, ensure_ascii=False, indent=2)
        modified_files.append(old_translations_path)

    old_segments_path = segments_dir / f"{chapter_id}.segments.json"
    if old_segments_path.exists():
        with old_segments_path.open("r", encoding="utf-8") as f:
            old_segments_data = json.load(f)
        
        old_segments = old_segments_data.get("segments", [])
        new_segments = []
        
        old_to_new_ids: Dict[str, List[str]] = {}
        for nid, old_ids in new_to_old_ids_map.items():
            for oid in old_ids:
                if oid not in old_to_new_ids:
                    old_to_new_ids[oid] = []
                if nid not in old_to_new_ids[oid]:
                    old_to_new_ids[oid].append(nid)

        processed_new_ids = set()
        
        for old_seg in old_segments:
            old_sids = old_seg.get("sentenceIds", [])
            new_sids_for_seg = []
            
            for oid in old_sids:
                if oid in old_to_new_ids:
                    mapped_new_ids = old_to_new_ids[oid]
                    for nid in mapped_new_ids:
                        if nid not in processed_new_ids:
                            new_sids_for_seg.append(nid)
                            processed_new_ids.add(nid)
            
            if new_sids_for_seg:
                new_seg = old_seg.copy()
                new_seg["sentenceIds"] = new_sids_for_seg
                new_segments.append(new_seg)

        for i, seg in enumerate(new_segments):
            seg["segmentIndex"] = i + 1
            seg["id"] = f"{chapter_num}-{i+1}"

        old_segments_data["segments"] = new_segments
        
        with old_segments_path.open("w", encoding="utf-8") as f:
            json.dump(old_segments_data, f, ensure_ascii=False, indent=2)
        modified_files.append(old_segments_path)

    real_sentences_path = sentences_dir / f"{chapter_id}.sentences.json"
    with real_sentences_path.open("w", encoding="utf-8") as f:
        output_data = {
            "chapterId": chapter_id,
            "number": chapter_num,
            "title": new_data.get("title", ""),
            "sentences": new_sentences_list
        }
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    modified_files.append(real_sentences_path)
    
    run_prettier(modified_files)


def main():
    root = Path(__file__).resolve().parent.parent.parent
    chapters_dir = root / "renderer" / "public" / "chapters"
    sentences_dir = root / "renderer" / "public" / "sentences"
    transcripts_dir = root / "renderer" / "public" / "transcripts"
    translations_dir = root / "renderer" / "public" / "translations"
    segments_dir = root / "renderer" / "public" / "segments"

    # Process all chapters 1-13
    for i in range(1, 14):
        migrate_chapter(
            i,
            chapters_dir,
            sentences_dir,
            translations_dir,
            transcripts_dir,
            segments_dir
        )


if __name__ == "__main__":
    main()
