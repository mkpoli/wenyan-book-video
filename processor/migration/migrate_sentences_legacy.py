from __future__ import annotations

import regex as re
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
import importlib.util

# Add current directory to sys.path to import sibling modules


def split_ipa(ipa_str: str, char_counts: List[int]) -> List[str]:
    """
    Split IPA string based on the number of Chinese characters in each segment.
    This assumes approximately 1 syllable per Chinese character.
    Note: IPA strings often have spaces or punctuation.
    We'll try to split by syllable count.
    """
    # This is heuristic. IPA string: "syllable1 syllable2 ..."
    # Syllables are separated by spaces or punctuation.
    # But punctuation might be attached?
    # Let's just tokenize by whitespace for now.
    tokens = ipa_str.split()

    # Filter out standalone punctuation if possible?
    # Or assume punctuation is part of the previous syllable or its own token?
    # In `c5-s40` example: "bʉòm liet ʈʉùŋ ʨɨ̀ː ŋʉòn ŋòː ɦʉúː ɲǐː ŋɨə̀n ."
    # Source: "凡「列」中之「元」" (7 chars) + "\n\t吾有二言。" (5 chars) -> Total 12 chars.
    # IPA Tokens:
    # 1. bʉòm (凡)
    # 2. liet (列)
    # 3. ʈʉùŋ (中)
    # 4. ʨɨ̀ː (之)
    # 5. ŋʉòn (元)
    # 6. ŋòː (吾)
    # 7. ɦʉúː (有)
    # 8. ɲǐː (二)
    # 9. ŋɨə̀n (言)
    # 10. . (punctuation)
    #
    # Wait, 9 syllables for 12 chars?
    # "凡「列」中之「元」" -> 5 chars (ignoring quotes).
    # "吾有二言" -> 4 chars (ignoring whitespace).
    # Total 9 meaningful chars.
    #
    # So we need to count MEANINGFUL Chinese characters (Han characters).
    #

    return []


def count_han_chars(text: str) -> int:
    # Count characters in Unicode Han range
    return len(re.findall(r"\p{Han}", text))


def split_transcript_data(
    original_ipa: str, original_tupa: str, new_segments: List[str]
) -> List[Dict[str, str]]:
    """
    Split IPA and Tupa strings corresponding to new segments.
    """
    segment_char_counts = [count_han_chars(s) for s in new_segments]
    total_chars = sum(segment_char_counts)

    if total_chars == 0:
        # No Han chars? Maybe just punctuation.
        # Return empty/duplicated strings?
        return [{"ipa": "", "tupa": ""} for _ in new_segments]

    ipa_tokens = original_ipa.split()
    tupa_tokens = original_tupa.split()

    # We assume tokens roughly correspond to syllables.
    # Punctuation tokens usually at the end or aligned with punctuation in text.
    # This is tricky. Punctuation in IPA/Tupa is usually separate token ".".

    # Simple strategy:
    # 1. Filter out non-syllable tokens? No, we need to keep them.
    # 2. Assume 1-to-1 mapping of Syllable Token -> Han Char.
    # 3. Distribute tokens based on char counts.
    # 4. Attach punctuation to preceding segment?

    # Let's identify "syllable-like" tokens vs "punctuation" tokens.
    # Or just count tokens?
    # In the example: 9 syllables + 1 dot = 10 tokens.
    # Chars: 9 chars.
    # So 1 syllable per char. Punctuation is extra.

    # Distribution:
    # Segment 1 (5 chars): Take first 5 syllable tokens.
    # Segment 2 (4 chars): Take next 4 syllable tokens.
    # Remaining tokens (punctuation): Attach to last segment? Or distribute?
    # Punctuation usually follows the sentence.

    ipa_results = []
    tupa_results = []

    ipa_idx = 0
    tupa_idx = 0

    ipa_len = len(ipa_tokens)
    tupa_len = len(tupa_tokens)

    for i, count in enumerate(segment_char_counts):
        # Grab syllables
        current_ipa = []
        current_tupa = []

        syllables_grabbed = 0
        while syllables_grabbed < count and ipa_idx < ipa_len:
            token = ipa_tokens[ipa_idx]
            # Check if token is punctuation?
            # Heuristic: starts with non-alphanumeric? or specific chars?
            # "." is punctuation.
            if token in [".", ",", "!", "?", "。", "，", "！", "？"]:
                current_ipa.append(token)
                ipa_idx += 1
                continue  # Don't count as syllable

            current_ipa.append(token)
            ipa_idx += 1
            syllables_grabbed += 1

        # Grab trailing punctuation for this segment
        # Only if it's not the start of the next syllable?
        # Actually, standard format puts space before punctuation "."
        while ipa_idx < ipa_len and ipa_tokens[ipa_idx] in [
            ".",
            ",",
            "!",
            "?",
            "。",
            "，",
            "！",
            "？",
        ]:
            current_ipa.append(ipa_tokens[ipa_idx])
            ipa_idx += 1

        # Do same for Tupa
        syllables_grabbed = 0
        while syllables_grabbed < count and tupa_idx < tupa_len:
            token = tupa_tokens[tupa_idx]
            if token in [".", ",", "!", "?", "。", "，", "！", "？"]:
                current_tupa.append(token)
                tupa_idx += 1
                continue

            current_tupa.append(token)
            tupa_idx += 1
            syllables_grabbed += 1

        while tupa_idx < tupa_len and tupa_tokens[tupa_idx] in [
            ".",
            ",",
            "!",
            "?",
            "。",
            "，",
            "！",
            "？",
        ]:
            current_tupa.append(tupa_tokens[tupa_idx])
            tupa_idx += 1

        ipa_results.append(" ".join(current_ipa))
        tupa_results.append(" ".join(current_tupa))

    # If any remaining tokens, append to last segment
    if ipa_idx < ipa_len and ipa_results:
        ipa_results[-1] += " " + " ".join(ipa_tokens[ipa_idx:])
    if tupa_idx < tupa_len and tupa_results:
        tupa_results[-1] += " " + " ".join(tupa_tokens[tupa_idx:])

    # Add trailing "." to segments that end before a "\n" split
    for i in range(len(ipa_results) - 1):
        if new_segments[i + 1].startswith("\n"):
            # Next segment starts with newline, so this segment should end with "."
            if not ipa_results[i].rstrip().endswith("."):
                ipa_results[i] = ipa_results[i].rstrip() + " ."

    results = [
        {"ipa": ipa, "tupa": tupa} for ipa, tupa in zip(ipa_results, tupa_results)
    ]
    return results


sys.path.append(str(Path(__file__).parent))

# Import build-sentences.py dynamically because of the hyphen
build_sentences_path = Path(__file__).parent / "build-sentences.py"
spec = importlib.util.spec_from_file_location("build_sentences", build_sentences_path)
build_sentences_module = importlib.util.module_from_spec(spec)
sys.modules["build_sentences"] = build_sentences_module
spec.loader.exec_module(build_sentences_module)

build_sentences_for_chapter = build_sentences_module.build_sentences_for_chapter


def normalize_text(text: str) -> str:
    """Normalize text for comparison (ignore whitespace differences)."""
    return "".join(text.split())


def migrate_chapter(
    chapter_num: int,
    chapters_dir: Path,
    sentences_dir: Path,
    translations_dir: Path,
    transcripts_dir: Path,
) -> List[Path]:
    """Migrate a chapter and return list of modified file paths."""
    modified_files: List[Path] = []
    chapter_id = f"c{chapter_num}"
    chapter_json_path = chapters_dir / f"{chapter_id}.json"
    old_sentences_path = sentences_dir / f"{chapter_id}.sentences.json"

    if not chapter_json_path.exists():
        print(f"Chapter {chapter_id} not found, skipping.")
        return modified_files

    if not old_sentences_path.exists():
        print(
            f"Old sentences for {chapter_id} not found, skipping migration logic (will just regenerate)."
        )
        # Just regenerate sentences
        build_sentences_for_chapter(chapter_json_path, sentences_dir)
        modified_files.append(old_sentences_path)
        return modified_files

    # 1. Read old sentences
    # Note: We MUST assume 'old_sentences' matches the current 'old_trans'/'old_transcript' keys.
    # If we already ran migration partially, 'old_sentences' might be the NEW split version,
    # but 'old_trans' might be the OLD unsplit version (if something failed), OR
    # 'old_trans' might be the NEW version too.

    # The issue reported is duplication. This happens if we map:
    # Old (already split): A -> New (split): A (match)
    # But maybe the IDs shifted?

    # Actually, if we run this script TWICE:
    # Run 1:
    # Old Sentences (Unsplit): S1 ("A\nB")
    # New Sentences (Split): S1' ("A"), S2' ("\nB")
    # Map: S1 -> [S1', S2']
    # Transcripts: S1 (content X) -> S1' (content X), S2' (content X)
    # Result: S1' and S2' both have content X. Correct (duplication intended for manual fix).
    # Sentences File Updated: S1 is gone, S1', S2' exist.

    # Run 2 (The Problem):
    # Old Sentences (Split): S1' ("A"), S2' ("\nB")  <-- Loaded from disk
    # New Sentences (Split): S1' ("A"), S2' ("\nB")  <-- Generated
    # Map:
    #   S1' -> S1' (Exact match)
    #   S2' -> S2' (Exact match)
    #
    # Transcripts (Already Split):
    #   S1' (content X)
    #   S2' (content X)
    #
    # Migration Logic:
    #   For Old ID S1': Map is [S1']
    #     Entry S1' (content X) -> New S1' (content X)
    #   For Old ID S2': Map is [S2']
    #     Entry S2' (content X) -> New S2' (content X)
    #
    # This looks idempotent. Why duplication?
    #
    # Let's look at the user's report:
    # c1.transcripts.json:
    # "c1-s208": "為是千遍。" (Translation/IPA seems fine)
    # "c1-s209": "\n\t吾有一言。" (IPA: "ɦỵèː ʥiéː ʦʰèn pěn ." - This matches s208!)
    #
    # Wait, s209 source is "\n\t吾有一言。", but IPA is "为是千遍" (s208's IPA).
    # This means s208 and s209 were split from a parent, say sOld.
    # sOld source: "\n\n為是千遍。\n\t吾有一言。"
    # sOld IPA: "為是千遍" stuff.
    #
    # Split 1:
    # s208 (New): "\n\n為是千遍。" -> gets sOld IPA.
    # s209 (New): "\n\t吾有一言。" -> gets sOld IPA.
    #
    # This IS what the script does: "duplicate the content to all resulting sentences".
    # The user says: "The sentences are correct, but ... the transcripts and others gets duplicated ... I believe this is due to reapplying destructive change twice".
    #
    # Ah, if I apply "Split on \n" (previous turn):
    # Old: "A\nB"
    # New: "A", "\nB"
    # Result: "A" gets full IPA, "\nB" gets full IPA.
    #
    # If I apply "Split on \n+" (current turn):
    # Old (from disk, already split by previous turn): "A", "\nB"
    # New (generated): "A", "\nB" (Assuming logic is consistent or cleaner)
    #
    # If the previous split was "A", "\n", "B" (maybe?)
    #
    # User says: "now "\n\n有數一。" becomes "\n" and "\n有數一。"" (Previous behavior)
    # "but it should not split before second "\n"" (Desired behavior)
    #
    # So previously we might have had:
    # S1: "\n"
    # S2: "\n有數一。"
    #
    # Now we want:
    # S_combined: "\n\n有數一。"
    #
    # If we migrate FROM the "Bad Split" state:
    # Old Sentences: S1 ("\n"), S2 ("\n有數一。")
    # New Sentences: S_new ("\n\n有數一。")
    #
    # My script's matching logic:
    # Match S1 ("\n") vs S_new ("\n\n有數一。") -> Mismatch.
    #
    # The script falls back to:
    # "Try split match (Old source contains New source)" -> No, Old is shorter.
    # "Accumulate new sentences until they match old source" -> New is longer.
    #
    # My script currently supports 1-to-Many (Old->New splits).
    # It does NOT support Many-to-1 (Old->New merges).
    #
    # If we are merging sentences back, the script will fail or misbehave.
    #
    # BUT, the user said: "The sentences are correct".
    # This implies `c*.sentences.json` IS updated and correct (merged back).
    #
    # Wait, I generated `c*.sentences.json` using `build-sentences.py` in the previous turn.
    # So `renderer/public/sentences/c*.sentences.json` ON DISK contains the CORRECT (merged) sentences.
    #
    # `migrate_split_sentences.py`:
    # line 52: `with old_sentences_path.open(...)` -> Reads the CORRECT sentences from disk as "old_sentences".
    # line 59: `build_sentences_for_chapter(..., temp_path)` -> Generates CORRECT sentences as "new_sentences".
    #
    # So `old_sentences` == `new_sentences`.
    # Mapping is 1-to-1.
    #
    # However, `translations` and `transcripts` on disk correspond to the PREVIOUS (bad split) state?
    #
    # No, I ran migration in the previous turn.
    # If I ran migration, I updated translations/transcripts to match the "New" (merged) state?
    #
    # Let's trace the previous turn:
    # 1. `build-sentences.py` modified to handle `\n+`.
    # 2. `run processor/build-sentences.py` -> Updates `c*.sentences.json` on disk.
    #    Now `c*.sentences.json` has "\n\n有數一。" (Merged).
    #
    # 3. `run processor/migrate_split_sentences.py`
    #    - Reads `old_sentences_path` (The Merged ones).
    #    - Generates `new_sentences` (The Merged ones).
    #    - Mapping is 1-to-1. ID S_merged -> ID S_merged.
    #    - Reads `translations_path`.
    #      This file likely has keys from the BEFORE-MERGE state (the "Bad Split" state).
    #      e.g. IDs S1, S2.
    #    - Loop: `for old_id, mapped in id_map:`
    #      old_id is S_merged.
    #      Check `if old_id in old_trans`:
    #      S_merged is a NEW ID (probably). S1, S2 are old IDs.
    #      So S_merged is NOT in `old_trans`.
    #      Result: Data for S_merged is lost/missing in the output?
    #
    # BUT the user sees duplication.
    # "c1-s208" and "c1-s209" in `c1.transcripts.json`.
    #
    # If the sentences are correct, `c1.sentences.json` should have:
    # c1-s208: "..."
    # c1-s209: "..."
    #
    # If the transcripts match these IDs, then the transcript file structure is correct vis-a-vis the sentences file.
    #
    # The issue is the CONTENT.
    # c1-s208 source: "\n\n為是千遍。"
    # c1-s209 source: "\n\t吾有一言。"
    #
    # User says: c1-s209 IPA is same as c1-s208.
    #
    # This implies that at some point, s208 and s209 were split from a single parent, and they both inherited the parent's IPA.
    #
    # Parent: "\n\n為是千遍。\n\t吾有一言。" (IPA for both)
    # Split -> s208, s209.
    #
    # If this split is CORRECT (i.e. they SHOULD be two sentences), then the "duplication" of IPA is just the intended behavior of the migration script (preserving data by duplicating).
    #
    # User says: "The sentences are correct".
    # So s208 and s209 SHOULD be separate.
    #
    # User says: "the transcripts and others gets duplicated ... I believe this is due to reapplying destructive change twice".
    #
    # If they should be separate, then s209 having s208's IPA is "wrong" content-wise (it's the IPA for the previous combined sentence), but "correct" logic-wise (we duplicated it).
    #
    # The user might be thinking that I messed up and mapped s208's IPA to s209 INCORRECTLY, not just "inherited from parent".
    #
    # Or maybe the user thinks they shouldn't be split?
    # "Treat consecutive `\n`s as a whole, so now "\n\n有數一。" becomes "\n" and "\n有數一。", but it should not split before second "\n""
    #
    # This request was about NOT splitting "\n\n" into "\n" + "\n...".
    # It was NOT about preventing split on "\n" in general.
    #
    # "\n\n為是千遍。" -> This looks like it starts with consecutive newlines. It is ONE sentence.
    # "\n\t吾有一言。" -> This is ANOTHER sentence.
    #
    # They are separated by what?
    # If source was "...\n\n為是千遍。\n\t吾有一言。", they are separated by `\n`.
    #
    # My logic: split on `\n` (or `\n+`).
    # So "A\nB" -> "A", "\nB".
    #
    # If "A" ends with `。`, and we have `\n`?
    #
    # Let's look at `c1-s208` source in the user snippet: `"\n\n為是千遍。"`.
    # `c1-s209` source: `"\n\t吾有一言。"`.
    #
    # The previous sentence `c1-s207` probably ended with `。`.
    #
    # The duplication issue:
    # The user implies that `c1-s209` has the WRONG IPA (copy of s208).
    # This happens because they were originally ONE block/sentence that got split?
    #
    # If they were originally one sentence, and now they are split, duplication is the default fallback.
    # The user might want me to "Fix" it?
    #
    # "Please check why and try to fix the problem".
    #
    # If I can't automatically determine which part of IPA belongs to which part of text (I can't easily), duplication is the safest "fix" to avoid data loss.
    #
    # BUT, maybe the user thinks I ran the migration TWICE and that caused weirdness?
    #
    # If I run migration twice:
    # 1. Split S -> S1, S2. (S1=IPA, S2=IPA).
    # 2. Migration again. S1->S1, S2->S2. No change.
    #
    # Unless... I am restoring files now.
    #
    # To fix "duplication", I would need to UNDO the split if it's wrong, OR intelligently split the metadata.
    #
    # If "The sentences are correct", then the split is correct.
    # Then the "duplication" is just the state of the data.
    #
    # Perhaps the user implies that `c1-s208` and `c1-s209` WERE ALREADY separate before, and I somehow merged them and re-split them, or mapped them wrong?
    #
    # Let's check `renderer/public/transcripts/c1.transcripts.json` (I restored it).
    # I need to see what it looked like BEFORE my latest migration.

    with old_sentences_path.open("r", encoding="utf-8") as f:
        old_data = json.load(f)
    old_sentences: List[Dict[str, Any]] = old_data["sentences"]

    # 2. Generate new sentences in temp dir
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        build_sentences_for_chapter(chapter_json_path, temp_path)

        new_sentences_path = temp_path / f"{chapter_id}.sentences.json"
        with new_sentences_path.open("r", encoding="utf-8") as f:
            new_data = json.load(f)
        new_sentences: List[Dict[str, Any]] = new_data["sentences"]

        # 3. Map old IDs to new IDs
        id_map: Dict[str, List[Dict[str, Any]]] = {}

        old_idx = 0
        new_idx = 0

        while old_idx < len(old_sentences) and new_idx < len(new_sentences):
            old_s = old_sentences[old_idx]
            new_s = new_sentences[new_idx]

            old_id = old_s["id"]
            old_source = old_s["source"]
            new_source = new_s["source"]

            # Normalize text for comparison
            norm_old = normalize_text(old_source)
            norm_new = normalize_text(new_source)

            # Exact match
            if norm_old == norm_new:
                id_map[old_id] = [new_s]
                old_idx += 1
                new_idx += 1
                continue

            # 1-to-Many Split (Old source contains New source)
            # Check if old_source starts with new_source
            if norm_old.startswith(norm_new):
                accumulated_new = [new_s]
                accumulated_text = norm_new

                curr_new_idx = new_idx + 1
                match_found = False

                while curr_new_idx < len(new_sentences):
                    next_new_s = new_sentences[curr_new_idx]
                    norm_next = normalize_text(next_new_s["source"])
                    accumulated_new.append(next_new_s)
                    accumulated_text += norm_next

                    if accumulated_text == norm_old:
                        match_found = True
                        break

                    if len(accumulated_text) > len(norm_old):
                        break

                    curr_new_idx += 1

                if match_found:
                    id_map[old_id] = accumulated_new
                    old_idx += 1
                    new_idx = curr_new_idx + 1
                    continue

            # Many-to-1 Merge (Old source is part of New source)
            # This handles the case where we previously split too aggressively (e.g. on "\n\n")
            # and now we are merging them back (e.g. "\n\n" + "Text").
            if norm_new.startswith(norm_old):
                accumulated_old_ids = [old_id]
                accumulated_text = norm_old

                curr_old_idx = old_idx + 1
                match_found = False

                while curr_old_idx < len(old_sentences):
                    next_old_s = old_sentences[curr_old_idx]
                    norm_next = normalize_text(next_old_s["source"])
                    accumulated_old_ids.append(next_old_s["id"])
                    accumulated_text += norm_next

                    if accumulated_text == norm_new:
                        match_found = True
                        break

                    if len(accumulated_text) > len(norm_new):
                        break

                    curr_old_idx += 1

                if match_found:
                    # We found multiple old sentences that merge into one new sentence.
                    # We map ALL old IDs to this ONE new sentence.
                    # But wait, the output is a dictionary of ID -> Entry.
                    # If we map multiple old IDs to one new ID, which old entry do we use?
                    # We should probably pick the one with the most meaningful content, or merge them?
                    # For simple migration, we can map the FIRST old ID to the new sentence,
                    # and ignore the others (or merge their text?).

                    # Actually, the goal is to preserve translation/transcript.
                    # If we merge S1 (Trans1) and S2 (Trans2) -> S_new.
                    # S_new should ideally have Trans1 + Trans2.
                    #
                    # Current structure of id_map: Old_ID -> List[New_Sentences].
                    # This supports 1-to-Many.
                    #
                    # For Many-to-1, we have:
                    # Old_ID_1 -> [S_new]
                    # Old_ID_2 -> [S_new]
                    # ...
                    # When generating translations:
                    # iterate old_ids.
                    # Old_ID_1: writes to S_new (overwrites/creates).
                    # Old_ID_2: writes to S_new (overwrites).
                    #
                    # This causes data loss (last one wins).
                    #
                    # We need a way to MERGE the data.
                    #
                    # Let's adjust the logic to handle this.

                    # Instead of id_map, let's build `new_trans` directly?
                    # No, we want to reuse logic.

                    # Let's store: New_ID -> List[Old_ID] mapping for merging?
                    #
                    # Or better: In the loop below (Migrate Translations), we need to know about this merge.

                    # Let's record this relationship.
                    for oid in accumulated_old_ids:
                        id_map[oid] = [new_s]  # This marks them all as mapping to new_s

                    # We need a special flag or structure to say "These old IDs merge to this New ID".
                    # But `id_map` is simple.

                    old_idx = curr_old_idx + 1
                    new_idx += 1
                    continue

            print(f"Warning: Mismatch at {old_id} vs {new_s['id']}")
            print(f"Old: {old_source}")
            print(f"New: {new_source}")

            # If we are here, we have a mismatch that isn't a simple split or merge.
            # But the user reports duplication in cases where it SHOULD work.
            #
            # Example Failure Mode:
            # Old: "A" (id: 1)
            # New: "A" (id: 1)
            # Old: "B" (id: 2) -- But assume "B" was actually "B\nC" in previous incorrect state?
            #
            # Wait, look at c4.transcripts.json (Restored):
            # c4-s129: "\n\n若「物」等於『禽獸』者。" (IPA correct)
            # c4-s130: "\n\t吾有一言。" (IPA correct)
            #
            # The user snippet (Duplicated):
            # c4-s129: "\n\n若「物」等於『禽獸』者。" (IPA correct)
            # c4-s130: "\n\t吾有一言。" (IPA: SAME AS s129! "ɲɨɑk mʉt...")
            #
            # Why did s130 get s129's IPA?
            #
            # Logic trace:
            # id_map[old_id] -> [new_sentences]
            #
            # If s130 got s129's IPA, it means s130 (New) was mapped to s129 (Old).
            # i.e., id_map[s129_Old] = [s129_New, s130_New]
            #
            # Why did s129_Old map to both?
            # "Split match (Old source contains New source)"
            #
            # s129_Old Source: "\n\n若「物」等於『禽獸』者。"
            # s129_New Source: "\n\n若「物」等於『禽獸』者。"
            #
            # norm(Old) == norm(New).
            #
            # My logic:
            # if normalize_text(old_source) == normalize_text(new_source):
            #    id_map[old_id] = [new_s]
            #    continue
            #
            # So s129_Old should map ONLY to s129_New.
            #
            # Then loop continues.
            # old_idx++ (points to s130_Old)
            # new_idx++ (points to s130_New)
            #
            # s130_Old Source: "\n\t吾有一言。"
            # s130_New Source: "\n\t吾有一言。"
            #
            # norm(Old) == norm(New).
            # id_map[s130_Old] = [s130_New].
            #
            # Result:
            # s129_New gets s129_Old content.
            # s130_New gets s130_Old content.
            #
            # This is CORRECT.
            #
            # So why did it fail before?
            #
            # "c4.transcripts.json (2324-2408) apparently the duplication appears again"
            #
            # Perhaps the `c4.sentences.json` ON DISK (which acts as `old_sentences`) was weird?
            #
            # When I run `migrate_split_sentences.py`:
            # 1. `old_sentences` = Load `c4.sentences.json`.
            # 2. `new_sentences` = Regenerate from `c4.json`.
            #
            # If `c4.sentences.json` was ALREADY generated in a previous step (which it was, via `build-sentences.py` in the previous turn), then:
            # `old_sentences` has:
            # s129: "\n\n若..."
            # s130: "\n\t吾..."
            #
            # `new_sentences` (Regenerated) should be IDENTICAL.
            #
            # So mapping should be 1-to-1.
            #
            # BUT, look at `c4.transcripts.json`.
            # The keys are `c4-s129`, `c4-s130`.
            #
            # If mapping is 1-to-1:
            # s129 (New) gets s129 (Old, Transcript) -> Correct.
            # s130 (New) gets s130 (Old, Transcript) -> Correct.
            #
            # So where does the duplication come from?
            #
            # Maybe `old_sentences` source text was DIFFERENT?
            #
            # If `old_sentences` had s129: "\n\n若...者。\n\t吾...。" (Combined)
            # And `new_sentences` had them split.
            #
            # Then s129 (Old) maps to [s129 (New), s130 (New)].
            # And s129 (Old, Transcript) is applied to BOTH.
            # s129 Transcript has "若...".
            # So s130 gets "若...".
            #
            # This implies `c4.sentences.json` on disk was COMBINED.
            #
            # BUT I ran `build-sentences.py` in the previous turn. It should have SPLIT them.
            #
            # Unless... my `build-sentences.py` logic for `\n+` caused them to MERGE?
            #
            # Let's check `build-sentences.py` change.
            #
            # Old logic (before my today's change):
            # `\n` is a delimiter.
            # "\n\n" -> sentence 1 ("\n"), sentence 2 ("\n...").
            #
            # New logic (my today's change):
            # `\n+` (consecutive newlines) is a single delimiter.
            #
            # Text: "\n\n若...者。\n\t吾..."
            #
            # `re.split(r'([。]|\n+)', text)`
            # -> [ "", "\n\n", "若...者", "。", "", "\n", "\t吾..." ]
            #
            # Sentence 1: "若...者。" (delimiters consumed/handled)
            # Sentence 2: "\t吾..." (starts with `\n` delimiter from split?)
            #
            # Wait, `split_sentences` logic:
            # `tokens = re.split(r'([。]|\n+)', text)`
            #
            # Loop tokens:
            # 1. "" (skip)
            # 2. "\n\n" (elif token.startswith("\n")) -> Delimiter.
            #    `current_parts` is empty. Nothing happens.
            # 3. "若...者" -> `current_parts.append`.
            # 4. "。" -> `current_parts.append`. Sentence "若...者。" added. `current_parts` reset.
            # 5. "" (skip)
            # 6. "\n" (elif token.startswith("\n")) -> Delimiter.
            #    `current_parts` is empty. Nothing happens.
            # 7. "\t吾..." -> `current_parts.append`.
            #
            # Result:
            # S1: "若...者。"
            # S2: "\t吾..."
            #
            # NOTE: The "\n" delimiters are DROPPED in `split_sentences` (Prose).
            #
            # BUT `split_chinese_sentences` (Code blocks, usually, but `build_sentences_for_chapter` calls `remove_markdown` then `split_chinese_sentences` for pure text? No.)
            #
            # `build-sentences.py` logic:
            # `blocks = ...`
            # For each block:
            #   `text = remove_markdown(...)`
            #   `sents = split_chinese_sentences(text)`
            #
            # `split_chinese_sentences` was ALSO updated.
            #
            # Updated `split_chinese_sentences`:
            # `elif char == "\n" ...`:
            #   Consume consecutive `\n`.
            #   Flush current sentence.
            #   `current_sentence = newlines` (Start next sentence with newlines).
            #
            # So:
            # Input: "...\n\n若..."
            # Previous char (maybe): "。"
            #
            # Loop hits first `\n`.
            # Collects `\n\n`.
            # Flushes previous (empty?).
            # `current_sentence` = ["\n", "\n"].
            #
            # Next chars: "若", "...", "者", "。"
            # `char` = "。" -> Flushes `current_sentence`.
            # Sentence: "\n\n若...者。"
            #
            # Next char: `\n`.
            # `current_sentence` = [].
            # Collects `\n`.
            # `current_sentence` = ["\n"].
            #
            # Next chars: "\t", "吾", ...
            # `char` = "。" -> Flushes.
            # Sentence: "\n\t吾...。"
            #
            # So `split_chinese_sentences` KEEPS the newlines at the start of the sentence.
            #
            # So we have:
            # S1: "\n\n若...者。"
            # S2: "\n\t吾...。"
            #
            # This seems correct behavior for `split_chinese_sentences` (preserving whitespace).
            #
            # Now, `c4.transcripts.json` keys.
            # S1 -> s129
            # S2 -> s130
            #
            # If `old_sentences` (on disk) had:
            # s129: "\n\n若...者。\n\t吾...。" (Combined)
            #
            # Then normalization of Old ("\n\n若...者。\n\t吾...。")
            # Starts with normalization of New S1 ("\n\n若...者。").
            #
            # And `accumulated_text` (S1 + S2) == Old.
            #
            # So S1 and S2 map to s129(Old).
            #
            # So s129(New) gets s129(Old) transcript. (Correct)
            # s130(New) gets s129(Old) transcript. (INCORRECT - s129 Old transcript only covers the first part).
            #
            # PROBABLE CAUSE:
            # `c4.sentences.json` on disk WAS merged (s129 contained both).
            #
            # Why?
            # Maybe a previous run of `build-sentences.py` produced merged sentences?
            # Or the `remove_markdown` logic change caused merging?
            #
            # `remove_markdown` change: `re.sub(r"\n+", "\n", text)` (when NOT preserving newlines).
            # BUT `build_sentences_for_chapter` calls `remove_markdown(..., preserve_newlines=True)`?
            #
            # Let's check `build_sentences_for_chapter` in `processor/build-sentences.py`.
            # I need to read it.

            # If I cannot verify why `c4.sentences.json` was merged, I can at least fix the migration logic.
            #
            # The migration logic assumes that if we split 1 -> Many, we should duplicate the metadata.
            # This is usually correct if we split a sentence that was "Atomic" in metadata (e.g. one big IPA string).
            #
            # But here, `c4.transcripts.json` (Restored) shows s129 and s130 ARE SEPARATE.
            # s129: "..."
            # s130: "..."
            #
            # So `transcripts.json` matches the SPLIT state.
            #
            # But `sentences.json` (Old) matched the MERGED state?
            #
            # This mismatch is the root cause.
            # `sentences.json` has s129 = "A + B".
            # `transcripts.json` has s129 = "A", s130 = "B".
            #
            # This state shouldn't happen if they are generated together.
            # But maybe I generated sentences, then didn't update transcripts, then generated sentences again (merged)?
            #
            # Regardless, the fix is:
            # When mapping Old (Merged) -> New (Split), we should check if `transcripts` (and `translations`) actually has entries for the *extra* keys that we think are "new".
            #
            # In the 1-to-Many case:
            # Old ID: s129.
            # New IDs: s129, s130.
            # Map: s129 -> [s129, s130].
            #
            # Migration loop:
            # Iterate map. old_id = s129.
            # mapped_new = [s129, s130].
            #
            # Loop new:
            # 1. new_s = s129. ID "s129".
            #    Apply s129(Old) transcript.
            # 2. new_s = s130. ID "s130".
            #    Apply s129(Old) transcript.  <-- HERE IS THE BUG.
            #
            # We are assuming s130 DOES NOT EXIST in the old transcript file because it wasn't in the old sentences file.
            # But in this "Partial State", s130 DOES exist in the old transcript file!
            #
            # So, before blindly applying the parent's (old_id) transcript to the child (new_id),
            # we should CHECK if `old_transcript` ALREADY HAS `new_id`.
            #
            # If `old_transcript` has `new_id`, we should prefer THAT over the `old_id`'s content (unless `old_id == new_id`).
            #
            # Fix Logic:
            # Inside the loop over `mapped_new_sentences`:
            #   new_id = new_s["id"]
            #   if new_id in old_trans:
            #       # The new ID already existed in the old data! Use that!
            #       new_trans[new_id] = old_trans[new_id]
            #   else:
            #       # Fallback to duplicating the parent (old_id) data
            #       new_trans[new_id] = old_trans[old_id]
            #
            # This handles the case where Sentences were merged (ID s129), but Transcripts were split (IDs s129, s130).
            # When we re-split Sentences (IDs s129, s130), we will now find s130 in Transcripts and preserve it.

            # Implementation details:
            # Need to modify both Translation and Transcript migration loops.

            # Let's verify this logic with the trace:
            # Map: s129 -> [s129, s130]
            #
            # Loop s129 (New):
            #   ID "s129".
            #   In old_trans? Yes.
            #   Use old_trans["s129"]. (Correct)
            #
            # Loop s130 (New):
            #   ID "s130".
            #   In old_trans? Yes.
            #   Use old_trans["s130"]. (Correct - Corrects the duplication!)
            #
            # Edge case:
            # What if s130 didn't exist?
            #   In old_trans? No.
            #   Use old_trans["s129"]. (Correct fallback for genuine split).

            pass

        # 4. Migrate Translations
        translations_path = translations_dir / f"{chapter_id}.translations.json"
        if translations_path.exists():
            with translations_path.open("r", encoding="utf-8") as f:
                old_trans = json.load(f)

            new_trans = {}

            # First pass: Handle 1-to-1 and 1-to-Many (Split)
            # and collect Many-to-1 (Merge) candidates
            merge_candidates: Dict[str, List[str]] = {}  # new_id -> list[old_id]

            for old_id, mapped_new_sentences in id_map.items():
                if old_id not in old_trans:
                    continue

                original_entry = old_trans[old_id]

                for new_s in mapped_new_sentences:
                    new_id = new_s["id"]

                    # Check if this new_id is already targeted by another old_id
                    # This indicates a Merge (Many-to-1)
                    if new_id in new_trans or new_id in merge_candidates:
                        if new_id not in merge_candidates:
                            # Move existing entry to candidates
                            # We need to find which old_id generated the existing entry?
                            # This is hard.
                            # Alternative: We build a reverse map first?
                            pass
                        if new_id not in merge_candidates:
                            merge_candidates[new_id] = []
                        merge_candidates[new_id].append(old_id)
                    else:
                        # Default case: 1-to-1 or 1-to-Many
                        # Check if the NEW ID actually exists in the OLD translations/transcripts
                        # This happens if sentences file was out of sync (merged) but translations were split.
                        if new_id in old_trans:
                            new_entry = old_trans[new_id].copy()
                        else:
                            new_entry = original_entry.copy()
                            # Conservatively empty translation for new splits to avoid duplication/confusion
                            # unless we are sure.
                            # User said: "for translations, try to empty it if you cannot decide."
                            if new_id not in old_trans:  # Only if it's a fresh split
                                new_entry["translation"] = ""

                        new_entry["source"] = new_s["source"]
                        new_trans[new_id] = new_entry

                        # Also track it as a potential merge target
                        if new_id not in merge_candidates:
                            merge_candidates[new_id] = [old_id]

            # Second pass: Handle Merges
            for new_id, old_ids in merge_candidates.items():
                if len(old_ids) > 1:
                    # Merge content
                    merged_translation = ""
                    # Sort old_ids by their numeric value to ensure order?
                    # Assuming id_map iteration order (which follows list order) is sufficient if preserved.
                    # old_ids list order depends on iteration order of `id_map`.
                    # Since Python 3.7+, dict insertion order is preserved.
                    # We iterated `old_sentences` in order, so `id_map` should be in order.

                    for oid in old_ids:
                        if oid in old_trans:
                            part = old_trans[oid].get("translation", "")
                            merged_translation += part + " "  # Simple join?

                    # Update the entry in new_trans
                    if new_id in new_trans:
                        new_trans[new_id]["translation"] = merged_translation.strip()

            # Write new translations
            translations_path.write_text(
                json.dumps(new_trans, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            modified_files.append(translations_path)
            print(f"Migrated translations for {chapter_id}")

        # 5. Migrate Transcripts
        transcripts_path = transcripts_dir / f"{chapter_id}.transcripts.json"
        if transcripts_path.exists():
            with transcripts_path.open("r", encoding="utf-8") as f:
                old_transcript = json.load(f)

            new_transcript = {}
            merge_candidates_tr: Dict[str, List[str]] = {}

            for old_id, mapped_new_sentences in id_map.items():
                if old_id not in old_transcript:
                    continue

                original_entry = old_transcript[old_id]
                original_ipa = original_entry.get("ipa", "")
                original_tupa = original_entry.get("tupa", "")

                # If we are splitting 1-to-Many
                if len(mapped_new_sentences) > 1:
                    # This is a REAL split - old_id is being split into multiple new sentences.
                    # We should ALWAYS perform the split from the parent's IPA/Tupa,
                    # rather than trusting existing child entries which may be from
                    # a previous incorrect migration.
                    new_sources = [s["source"] for s in mapped_new_sentences]
                    split_data = split_transcript_data(
                        original_ipa, original_tupa, new_sources
                    )
                    print(
                        f"  Split {old_id} into {len(mapped_new_sentences)} parts: {[s['id'] for s in mapped_new_sentences]}"
                    )
                else:
                    split_data = []

                for idx, new_s in enumerate(mapped_new_sentences):
                    new_id = new_s["id"]

                    if new_id in new_transcript or new_id in merge_candidates_tr:
                        if new_id not in merge_candidates_tr:
                            merge_candidates_tr[new_id] = []
                        merge_candidates_tr[new_id].append(old_id)
                    else:
                        # Check if existing entry is correct before overwriting
                        if new_id in old_transcript:
                            old_entry = old_transcript[new_id]
                            old_src_norm = normalize_text(old_entry.get("source", ""))
                            new_src_norm = normalize_text(new_s["source"])

                            # If source matches and IPA/Tupa seem correct, preserve it
                            if old_src_norm == new_src_norm:
                                old_ipa = old_entry.get("ipa", "")
                                old_ipa_tokens = old_ipa.split()
                                old_ipa_syllables = [
                                    t
                                    for t in old_ipa_tokens
                                    if t
                                    not in [".", ",", "!", "?", "。", "，", "！", "？"]
                                ]
                                sent_han_count = count_han_chars(new_s["source"])

                                # If IPA syllable count is reasonable for this sentence, keep it
                                if (
                                    len(old_ipa_syllables) >= sent_han_count * 0.7
                                    and len(old_ipa_syllables) <= sent_han_count * 1.5
                                ):
                                    new_entry = old_entry.copy()
                                    new_entry["source"] = new_s["source"]
                                    new_transcript[new_id] = new_entry
                                    if new_id not in merge_candidates_tr:
                                        merge_candidates_tr[new_id] = [old_id]
                                    continue

                        # Use split data if available
                        if split_data and idx < len(split_data):
                            new_entry = original_entry.copy()
                            split_ipa = split_data[idx]["ipa"]
                            split_tupa = split_data[idx]["tupa"]

                            # Add trailing "." if sentence ends before a "\n" split
                            # Check if this is not the last part and next part starts with "\n"
                            if idx < len(mapped_new_sentences) - 1:
                                next_sent = mapped_new_sentences[idx + 1]
                                if next_sent["source"].startswith(
                                    "\n"
                                ) and not split_ipa.rstrip().endswith("."):
                                    split_ipa = split_ipa.rstrip() + " ."

                            new_entry["ipa"] = split_ipa
                            new_entry["tupa"] = split_tupa
                            if "choices" in new_entry:
                                del new_entry["choices"]
                        else:
                            # No split data and no correct existing entry, use parent data (duplication)
                            new_entry = original_entry.copy()

                        new_entry["source"] = new_s["source"]
                        new_transcript[new_id] = new_entry

                        if new_id not in merge_candidates_tr:
                            merge_candidates_tr[new_id] = [old_id]

            # Handle Merges for Transcripts
            for new_id, old_ids in merge_candidates_tr.items():
                if len(old_ids) > 1:
                    # Merge content
                    merged_ipa = ""
                    merged_tupa = ""
                    # Merging choices is hard. We might lose choice data or have to concat lists?
                    # For now, let's just merge strings.

                    for oid in old_ids:
                        if oid in old_transcript:
                            part_ipa = old_transcript[oid].get("ipa", "")
                            part_tupa = old_transcript[oid].get("tupa", "")
                            merged_ipa += part_ipa + " "
                            merged_tupa += part_tupa + " "

                    if new_id in new_transcript:
                        new_transcript[new_id]["ipa"] = merged_ipa.strip()
                        new_transcript[new_id]["tupa"] = merged_tupa.strip()
                        # Clear choices to avoid mismatch
                        if "choices" in new_transcript[new_id]:
                            del new_transcript[new_id]["choices"]

            # Write new transcripts
            transcripts_path.write_text(
                json.dumps(new_transcript, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            modified_files.append(transcripts_path)
            print(f"Migrated transcripts for {chapter_id}")

        # 6. Replace sentences file
        shutil.copy(new_sentences_path, old_sentences_path)
        modified_files.append(old_sentences_path)
        print(f"Updated sentences for {chapter_id}")

    return modified_files


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    public_dir = root / "renderer" / "public"
    chapters_dir = public_dir / "chapters"
    sentences_dir = public_dir / "sentences"
    translations_dir = public_dir / "translations"
    transcripts_dir = public_dir / "transcripts"

    if not chapters_dir.exists():
        print(f"Chapters directory not found: {chapters_dir}")
        return

    chapter_files = sorted(chapters_dir.glob("c*.json"))
    all_modified_files: List[Path] = []

    for chapter_file in chapter_files:
        chapter_num = int(chapter_file.stem.lstrip("c"))
        print(f"Migrating Chapter {chapter_num}...")
        try:
            modified_files = migrate_chapter(
                chapter_num,
                chapters_dir,
                sentences_dir,
                translations_dir,
                transcripts_dir,
            )
            all_modified_files.extend(modified_files)
        except Exception as e:
            print(f"Error migrating chapter {chapter_num}: {e}")
            # Continue with other chapters? Or stop?
            # Stop to prevent partial corrupt state if possible
            # return

    print("Migration of sentences, translations, and transcripts complete.")

    # Format only affected JSON files with prettier for consistency
    if all_modified_files:
        print(
            f"Formatting {len(all_modified_files)} modified JSON files with prettier..."
        )
        try:
            # Convert Path objects to strings for prettier
            file_paths = [str(f) for f in all_modified_files]
            subprocess.run(
                ["bunx", "prettier", "--write"] + file_paths,
                check=True,
                cwd=root,
            )
            print("Prettier formatting complete.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Prettier formatting failed: {e}")
        except FileNotFoundError:
            print("Warning: Prettier not found. Skipping formatting.")

    print(
        "Run 'processor/segment-text.py' (or via 'bun run scripts/generate-segments.ts' in renderer) to update segments."
    )


if __name__ == "__main__":
    main()
