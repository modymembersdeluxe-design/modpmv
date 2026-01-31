"""
Parsing dispatcher (V3):
- Accepts: .it, .xm, .mod using OpenMPT adapter when available
- Fallback to text .mod parser (simple human-readable format)
- Normalizes output into a `module_data` dict consumed by renderers
"""
from typing import Dict, Any, List
import os

def _parse_text_mod(path: str) -> Dict[str, Any]:
    # Minimal text parser preserved from previous versions
    title = "Untitled"
    samples = {}
    patterns = []
    order = []
    section = None
    cur_pattern = []
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
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
                for p in parts[1:]:
                    if p.startswith("path="):
                        file = p.split("=",1)[1].strip()
                        if file and not os.path.isabs(file):
                            file = os.path.normpath(os.path.join(os.path.dirname(path), file))
                samples[name] = {"file": file}
                continue
            if u.startswith("PATTERN:"):
                section = "pattern"
                if cur_pattern:
                    patterns.append(cur_pattern)
                    cur_pattern = []
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
    if cur_pattern:
        patterns.append(cur_pattern)

    # normalize to 32 channels (max) for the text fallback
    channels = 32
    norm_patterns = []
    for patt in patterns:
        pat_norm = []
        for row in patt:
            r = row[:]
            if len(r) < channels:
                r += ["REST"] * (channels - len(r))
            else:
                r = r[:channels]
            pat_norm.append(r)
        norm_patterns.append(pat_norm)

    return {
        "title": title,
        "samples": samples,
        "patterns": norm_patterns,
        "order": order or list(range(len(norm_patterns))),
        "channels": channels,
        "duration_hint": None
    }

def parse(path: str) -> Dict[str, Any]:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".it", ".xm", ".mod"):
        # attempt OpenMPT via adapter
        try:
            from .openmpt_adapter import load_module_from_bytes
        except Exception:
            # No adapter available: fall back to text mod only if file is text; otherwise raise ImportError
            raise ImportError("No OpenMPT adapter available. Install a binding (e.g. pyopenmpt) to parse binary tracker modules.")
        # read bytes and attempt to create wrapper
        with open(path, "rb") as fh:
            data = fh.read()
        modwrap = load_module_from_bytes(data)
        title = getattr(modwrap, "title", os.path.splitext(os.path.basename(path))[0])
        channels = getattr(modwrap, "num_channels", 32) or 32
        channels = max(1, min(32, int(channels)))
        samples = {}
        try:
            for s in modwrap.sample_names():
                samples[s] = {"file": None}
        except Exception:
            samples = {}
        patterns = []
        try:
            npatt = modwrap.num_patterns()
            for p in range(npatt):
                rows = modwrap.pattern_rows(p)
                # normalize rows to channel count
                norm_rows = []
                for r in rows:
                    rr = r[:]
                    if len(rr) < channels:
                        rr += ["REST"] * (channels - len(rr))
                    else:
                        rr = rr[:channels]
                    norm_rows.append(rr)
                patterns.append(norm_rows)
        except Exception:
            patterns = [[["REST"]*channels for _ in range(4)]]
        order = modwrap.order_list() or list(range(len(patterns)))
        return {
            "title": title,
            "samples": samples,
            "patterns": patterns,
            "order": order,
            "channels": channels,
            "duration_hint": None
        }
    else:
        return _parse_text_mod(path)