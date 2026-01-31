"""
Parsing dispatcher (Deluxe).

- For binary .it/.xm/.mod files: uses openmpt_adapter.load_module_from_bytes (if available).
- For text modules: fallback _parse_text.
- Normalizes to module_data used by renderers.
"""
import os
from typing import Dict, Any

def _parse_text(path: str) -> Dict[str, Any]:
    title="Untitled"; samples={}; patterns=[]; order=[]; section=None; cur=[]
    with open(path,"r",encoding="utf-8",errors="ignore") as fh:
        for raw in fh:
            ln = raw.strip()
            if not ln or ln.startswith("#"): continue
            u = ln.upper()
            if u.startswith("TITLE:"): title = ln.split(":",1)[1].strip(); continue
            if u.startswith("SAMPLE:"):
                rest = ln.split(":",1)[1].strip()
                parts = [p.strip() for p in rest.split(",") if p.strip()]
                name = parts[0]; file=None
                for p in parts[1:]:
                    if p.startswith("path="):
                        file = p.split("=",1)[1].strip()
                        if file and not os.path.isabs(file):
                            file = os.path.normpath(os.path.join(os.path.dirname(path), file))
                samples[name]={"file":file}
                continue
            if u.startswith("PATTERN:"):
                section="pattern"
                if cur: patterns.append(cur); cur=[]
                continue
            if u.startswith("ORDER:"):
                order = [int(x) for x in ln.split(":",1)[1].split(",") if x.strip().isdigit()]; section=None; continue
            if section=="pattern":
                tokens=[]
                for tok in ln.replace(","," ").split():
                    tokens.append(tok.strip())
                if tokens: cur.append(tokens)
    if cur: patterns.append(cur)
    channels=32; norm=[]
    for patt in patterns:
        pn=[]
        for row in patt:
            r=row[:]
            if len(r)<channels: r+=["REST"]*(channels-len(r))
            else: r=r[:channels]
            pn.append(r)
        norm.append(pn)
    return {"title":title,"samples":samples,"patterns":norm,"order":order or list(range(len(norm))),"channels":channels,"duration_hint":None}

def parse(path: str) -> Dict[str, Any]:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".it",".xm",".mod"):
        try:
            from .openmpt_adapter import load_module_from_bytes
        except Exception as e:
            raise ImportError("OpenMPT adapter not available. Install 'pyopenmpt' or 'omp4py'. Adapter import error: "+str(e))
        with open(path,"rb") as fh:
            data = fh.read()
        try:
            modwrap = load_module_from_bytes(data)
        except Exception as e:
            raise RuntimeError("OpenMPT adapter failed to create module wrapper:\n\n" + str(e))
        title = getattr(modwrap, "title", os.path.splitext(os.path.basename(path))[0]) or os.path.splitext(os.path.basename(path))[0]
        channels = getattr(modwrap, "num_channels", 32) or 32
        channels = max(1, min(32, int(channels)))
        samples={}
        try:
            for s in modwrap.sample_names(): samples[s]={"file":None}
        except Exception:
            samples={}
        patterns=[]
        try:
            npat = modwrap.num_patterns()
            for p in range(npat):
                rows = modwrap.pattern_rows(p)
                norm_rows=[]
                for r in rows:
                    rr = list(r) if isinstance(r,(list,tuple)) else [r]
                    if len(rr) < channels: rr += ["REST"]*(channels-len(rr))
                    else: rr = rr[:channels]
                    norm_rows.append(rr)
                patterns.append(norm_rows)
        except Exception:
            patterns=[[["REST"]*channels for _ in range(4)]]
        try:
            order = modwrap.order_list() or list(range(len(patterns)))
        except Exception:
            order = list(range(len(patterns)))
        return {"title":title,"samples":samples,"patterns":patterns,"order":order,"channels":channels,"duration_hint":None}
    else:
        return _parse_text(path)