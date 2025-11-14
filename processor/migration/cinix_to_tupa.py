from __future__ import annotations

from typing import Dict, Tuple

import unicodedata


def _separate_tone(rhyme: str) -> Tuple[str, str]:
    """Separate the tone diacritic from the rhyme, mirroring cinix.ts."""
    ACCUTE_ACCENT = "\u0301"
    GRAVE_ACCENT = "\u0300"
    CARON = "\u030c"
    ORIGINAL_TONES = (ACCUTE_ACCENT, GRAVE_ACCENT, CARON)

    for tone in ORIGINAL_TONES:
        if tone in rhyme:
            return rhyme.replace(tone, ""), tone
    return rhyme, ""


def _convert_cinix_word_to_tupa(word: str) -> str:
    """
    Convert a single Cinix IPA syllable to TUPA transcription.

    This is a Python port of `convertWord` in `transcription-utils/cinix.ts`.
    """
    if not word:
        return ""

    result = unicodedata.normalize("NFD", word)

    # Split into onset + rhyme
    onset = ""
    rhyme = ""
    for idx, ch in enumerate(result):
        if ch and ch in "aeiouɑɨəʉyʷ":
            onset = result[:idx]
            rhyme = result[idx:]
            break
    else:
        onset = result
        rhyme = ""

    ONSET_TABLE: Dict[str, str] = {
        # Bilabial
        "p": "p",
        "pʰ": "ph",
        "b": "b",
        "m": "m",
        # Alveolar
        "t": "t",
        "tʰ": "th",
        "d": "d",
        "n": "n",
        "s": "s",
        "z": "z",
        "ʦ": "ts",
        "ʣ": "dz",
        "ʦʰ": "tsh",
        # Alveolo-palatal
        "ɕ": "sj",
        "ʑ": "zj",
        "ʨ": "tj",
        "ʨʰ": "tjh",
        "ʥ": "dj",
        "ɲ": "nj",
        # Retroflex
        "ʂ": "sr",
        "ʈ": "tr",
        "ɖ": "dr",
        "ɳ": "nr",
        "ꭧ": "tsr",
        "ꭧʰ": "tshr",
        "ꭦ": "dzr",
        "l": "l",
        # Palatal
        "j": "j",
        # Velar
        "k": "k",
        "kʰ": "kh",
        "g": "g",
        "ŋ": "ng",
        # Others
        "h": "h",
        "ʔ": "q",
        "ɦ": "gh",
    }

    onset = ONSET_TABLE.get(onset, onset)

    # Remove vowel length mark
    rhyme = rhyme.replace("ː", "")

    medial_nucleus = ""
    coda = ""
    for i in range(len(rhyme) - 1, -1, -1):
        ch = rhyme[i]
        if ch and ch not in "mnŋptkjw":
            coda = rhyme[i + 1 :]
            medial_nucleus = rhyme[: i + 1]
            break

    toneless_medial_nucleus, tone = _separate_tone(medial_nucleus)

    ACCUTE_ACCENT = "\u0301"
    GRAVE_ACCENT = "\u0300"
    CARON = "\u030c"
    TONE_TABLE: Dict[str, str] = {
        ACCUTE_ACCENT: "q",
        GRAVE_ACCENT: "",
        CARON: "h",
    }
    tone = TONE_TABLE.get(tone, tone)

    toneless_medial_nucleus = unicodedata.normalize("NFC", toneless_medial_nucleus)

    medial = ""
    nucleus = ""
    if len(toneless_medial_nucleus) == 1:
        nucleus = toneless_medial_nucleus
    elif len(toneless_medial_nucleus) == 2:
        medial = toneless_medial_nucleus[0]
        nucleus = toneless_medial_nucleus[1]
    elif len(toneless_medial_nucleus) > 2:
        medial = toneless_medial_nucleus[:-1]
        nucleus = toneless_medial_nucleus[-1]

    SPECIAL_PAIRS: Dict[str, str] = {
        "ɨə": "yo",
        "ʉu": "u",
    }

    pair = medial + nucleus
    if pair in SPECIAL_PAIRS:
        converted = SPECIAL_PAIRS[pair]
        medial = ""
        nucleus = converted
    else:
        MEDIAL_TABLE: Dict[str, str] = {
            "y": "wi",
            "ʷ": "w",
            "ɨ": "y",
            "ị": "y",
            "ʉ": "u",
            "ỵ": "u",
            "i": "i",
        }
        if medial:
            medial = MEDIAL_TABLE.get(medial, medial)

        NUCLEUS_TABLE: Dict[str, str] = {
            "a": "ae",
            "ạ": "ae",
            "e": "e",
            "ẹ": "ee",
            "ɑ": "a",
            "ə": "eo",
            "i": "i",
            "ɨ": "y",
            "ị": "yi",
            "u": "ou",
            "ʉ": "u",
            "o": "o",
            "ọ": "oeu",
        }
        if nucleus:
            nucleus = NUCLEUS_TABLE.get(nucleus, nucleus)

    CODA_TABLE: Dict[str, str] = {
        "m": "m",
        "n": "n",
        "ŋ": "ng",
        "p": "p",
        "t": "t",
        "k": "k",
        "w": "w",
        "j": "j",
    }
    if coda:
        coda = CODA_TABLE.get(coda, coda)

    # Avoid gh + u/y combinations
    if (onset == "gh" and nucleus in ("u", "y")) or (
        onset == "gh" and medial in ("u", "y")
    ):
        onset = ""

    result = "".join([onset, medial, nucleus, coda, tone])
    return unicodedata.normalize("NFC", result)


def convert_cinix_to_tupa(ipa: str) -> str:
    """
    Convert a Cinix IPA string to TUPA transcription, word by word.

    This mirrors `convertCinixToTUPA` (re-export of `convertIPAToTranscription`)
    from the `transcription-utils` TypeScript module.
    """
    if not ipa:
        return ""

    # JS version ignores "." sentence markers when converting Cinix to TUPA.
    parts = [p for p in ipa.split() if p and p != "."]
    converted = [_convert_cinix_word_to_tupa(word) for word in parts]
    return " ".join(converted).strip()


