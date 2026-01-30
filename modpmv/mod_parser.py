"""
ModPMV V2: simple, extensible .mod-like parser (text-based starter).

Format (text):
  TITLE: My Track
  SAMPLE: name[,path=assets/audio_samples/name.wav]
  PATTERN:
    SAMPLE:name SAMPLE:other REST
    SAMPLE:kick SAMPLE:snare
  ORDER: 0,1,0

This parser is intentionally straightforward and easy to extend to binary formats.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
import os

@dataclass
class Sample:
    name: str
    file: Optional[str] = None
    meta: Dict = None

@dataclass
class Pattern:
    rows: List[List[str]]

@dataclass
class Module:
    title: str
    samples: Dict[str, Sample]
    patterns: List[Pattern]
    order: List[int]

def parse_mod_text(path: str) -> Module:
    title = "Untitled"
    samples: Dict[str, Sample] = {}
    patterns: List[Pattern] = []
    order: List[int] = []
    section = None
    cur_pattern: List[List[str]] = []

    def flush_pattern():
        nonlocal cur_pattern
        if cur_pattern:
            patterns.append(Pattern(rows=cur_pattern))
            cur_pattern = []

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            ln = raw.strip()
            if not ln or ln.startswith("#"):
                continue
            u = ln.upper()
            if u.startswith("TITLE:"):
                title = ln.split(":",1)[1].strip()
                continue
            if u.startswith("SAMPLE:"):
                rest = ln.split(":",1)[1].strip()
                parts = [p.strip() for p in rest.split(",") if p.strip()]
                name = parts[0]
                file = None
                meta = {}
                for p in parts[1:]:
                    if p.startswith("path="):
                        file = p.split("=",1)[1].strip()
                        if file and not os.path.isabs(file):
                            file = os.path.normpath(os.path.join(os.path.dirname(path), file))
                    else:
                        kv = p.split("=",1)
                        if len(kv) == 2:
                            meta[kv[0].strip()] = kv[1].strip()
                samples[name] = Sample(name=name, file=file, meta=meta)
                continue
            if u.startswith("PATTERN:"):
                section = "pattern"
                flush_pattern()
                continue
            if u.startswith("ORDER:"):
                order = [int(x) for x in ln.split(":",1)[1].split(",") if x.strip().isdigit()]
                section = None
                continue
            if section == "pattern":
                tokens = []
                for tok in ln.replace(",", " ").split():
                    tokens.append(tok.strip())
                if tokens:
                    cur_pattern.append(tokens)
    flush_pattern()
    return Module(title=title, samples=samples, patterns=patterns, order=order)