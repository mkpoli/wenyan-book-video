from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Dict, List, Optional
import regex as re


# ---------- Data Models ----------

@dataclass(slots=True)
class Reading:
    transcription: str
    meaning: Optional[str] = None
    frequency: int = 0


@dataclass(slots=True)
class Segment:
    surface: str
    readings: list[Reading]

    @property
    def top(self) -> Optional[Reading]:
        return self.readings[0] if self.readings else None


# ---------- Optional Meaning Provider (plug-in) ----------

class MeaningProvider(Protocol):
    """
    Provide meanings for given characters.
    Return: { char: [Reading or dict-like payloads with .meaning/.transcription/.frequency] }
    Only .meaning is required; other fields, if present, are used to enrich.
    """
    def lookup(self, chars: str) -> dict[str, list[dict]]:
        ...


# ---------- Dictionary Loader ----------

def load_dictionary_tsv(path: Path | str) -> dict[str, list[Reading]]:
    """
    TSV format (no header):
        <char>\t<transcription>\t<frequency>
    """
    path = Path(path)
    mapping: dict[str, list[Reading]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        ch, trans, freq_s = parts
        try:
            freq = int(freq_s)
        except ValueError:
            freq = 0
        mapping.setdefault(ch, []).append(Reading(transcription=trans, frequency=freq))

    # sort by frequency desc
    for ch, items in mapping.items():
        items.sort(key=lambda r: r.frequency, reverse=True)
    return mapping


def load_dictionary_from_lines(lines: Iterable[str]) -> dict[str, list[Reading]]:
    mapping: dict[str, list[Reading]] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        ch, trans, freq_s = parts
        try:
            freq = int(freq_s)
        except ValueError:
            freq = 0
        mapping.setdefault(ch, []).append(Reading(transcription=trans, frequency=freq))
    for ch, items in mapping.items():
        items.sort(key=lambda r: r.frequency, reverse=True)
    return mapping


# ---------- Transcriber Core ----------

UNKNOWN_MEANING = "(無對應轉寫)"

class Transcriber:
    def __init__(
        self,
        dictionary: dict[str, list[Reading]],
        meaning_provider: MeaningProvider | None = None,
        *,
        enforce_limit: Optional[int] = 100,  # mirror the UI cap; set None to disable
    ) -> None:
        self.dictionary = dictionary
        self.meaning_provider = meaning_provider
        self.enforce_limit = enforce_limit

    def transcribe(self, text: str) -> list[Segment]:
        """
        Strip whitespace; optionally cap length; produce Segment list.
        """
        normalized = re.sub(r"\s+", "", text)
        if self.enforce_limit is not None and len(normalized) > self.enforce_limit:
            normalized = normalized[: self.enforce_limit]

        # collect chars that lack meanings to optionally enrich
        missing: set[str] = set()
        for ch in normalized:
            readings = self.dictionary.get(ch)
            if not readings:
                continue
            if any(r.meaning is None for r in readings):
                missing.add(ch)

        # optional fill meanings
        if self.meaning_provider and missing:
            try:
                payload = self.meaning_provider.lookup("".join(sorted(missing)))
                for ch, items in payload.items():
                    # align by index; if lengths differ, extend
                    existing = self.dictionary.setdefault(ch, [])
                    for idx, item in enumerate(items):
                        meaning = item.get("meaning")
                        trans = item.get("transcription")
                        freq = int(item.get("frequency", 0)) if "frequency" in item else None
                        if idx < len(existing):
                            # only fill missing fields; keep original transcription/freq ordering
                            if existing[idx].meaning is None and meaning:
                                existing[idx].meaning = meaning
                            if trans and trans != existing[idx].transcription:
                                # new variant: append instead of overwriting existing
                                existing.append(
                                    Reading(transcription=trans, meaning=meaning, frequency=freq or 0)
                                )
                            if freq is not None and freq > existing[idx].frequency:
                                existing[idx].frequency = freq
                        else:
                            # extend with new reading
                            existing.append(
                                Reading(
                                    transcription=trans or existing[0].transcription if existing else ch,
                                    meaning=meaning,
                                    frequency=freq or 0,
                                )
                            )
                    # keep highest frequency first
                    existing.sort(key=lambda r: r.frequency, reverse=True)
            except Exception:
                # soft-fail: keep whatever we already have
                pass

        # build segments
        segments: list[Segment] = []
        for ch in normalized:
            readings = self.dictionary.get(ch)
            if not readings:
                segments.append(
                    Segment(
                        surface=ch,
                        readings=[Reading(transcription=ch, meaning=UNKNOWN_MEANING, frequency=0)],
                    )
                )
                continue

            # copy readings so we don't mutate original dict entries
            copied: list[Reading] = []
            for r in readings:
                copied.append(
                    Reading(
                        transcription=r.transcription,
                        meaning=r.meaning if r.meaning is not None else None,
                        frequency=r.frequency,
                    )
                )

            # ensure at least the top reading has a meaning; fall back to unknown marker
            if copied and copied[0].meaning is None:
                copied[0].meaning = UNKNOWN_MEANING

            segments.append(Segment(surface=ch, readings=copied))

        return segments


# ---------- Convenience Free Function ----------

def transcribe(text: str, /, *, dictionary: dict[str, list[Reading]]) -> list[Segment]:
    """
    Simple helper if you don't need a MeaningProvider.
    """
    return Transcriber(dictionary).transcribe(text)
