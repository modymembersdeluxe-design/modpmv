"""
Simple .mod-like parser (starter).
This is a minimal illustrative parser. Real .mod formats (ProTracker, FastTracker) are more complex;
replace this with a proper spec-driven parser once you provide sample .mod files.
"""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Sample:
    name: str
    length: int
    data: bytes  # placeholder; real parser would extract PCM data or sample index

@dataclass
class Pattern:
    rows: List[List[str]]  # simplistic representation: list of rows, each row is list of commands/notes

@dataclass
class Module:
    title: str
    samples: List[Sample]
    patterns: List[Pattern]
    order: List[int]

def parse_mod_text(path: str) -> Module:
    """
    Very naive text-based .mod parser for demo purposes.
    Expects a simple human-readable format:
      TITLE: ...
      SAMPLE: name,length
      PATTERN:
        row1
        row2
    """
    title = "Untitled"
    samples = []
    patterns = []
    order = []
    with open(path, "r", encoding="utf-8") as f:
        section = None
        cur_pattern = []
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            if ln.startswith("TITLE:"):
                title = ln.split(":",1)[1].strip()
            elif ln.startswith("SAMPLE:"):
                parts = ln.split(":",1)[1].split(",")
                name = parts[0].strip()
                length = int(parts[1].strip()) if len(parts) > 1 else 0
                samples.append(Sample(name=name, length=length, data=b""))
            elif ln.startswith("PATTERN:"):
                if cur_pattern:
                    patterns.append(Pattern(rows=cur_pattern))
                    cur_pattern = []
                section = "pattern"
            elif ln.startswith("ORDER:"):
                order = [int(x) for x in ln.split(":",1)[1].split(",") if x.strip().isdigit()]
            else:
                if section == "pattern":
                    cur_pattern.append(ln.split())
        if cur_pattern:
            patterns.append(Pattern(rows=cur_pattern))
    return Module(title=title, samples=samples, patterns=patterns, order=order)