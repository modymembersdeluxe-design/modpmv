"""
OpenMPT adapter (Deluxe) — tries multiple bindings and provides detailed diagnostics.

Supports: pyopenmpt, omp4py, openmpt-like bindings. If a binding exists but constructors fail,
the adapter raises a descriptive RuntimeError containing attempted constructors and top-level attributes.
"""
from typing import Any, List, Tuple
import traceback

_BINDING_CANDIDATES = ("pyopenmpt", "openmpt", "omp4py", "libopenmpt", "pymodopenmpt")

_binding = None
_binding_name = None
for name in _BINDING_CANDIDATES:
    try:
        m = __import__(name)
        _binding = m
        _binding_name = name
        break
    except Exception:
        _binding = None
        _binding_name = None

def _list_attrs(bind) -> List[str]:
    try:
        return sorted(a for a in dir(bind) if not a.startswith("_"))
    except Exception:
        return []

def _attempt_constructors(bind, data: bytes) -> Tuple[Any, List[Tuple[str,str]]]:
    attempts = []
    raw = None
    def try_call(desc, fn):
        nonlocal raw
        if raw is not None:
            attempts.append((desc, "SKIPPED"))
            return
        try:
            val = fn()
            if val is not None:
                raw = val
            attempts.append((desc, "OK" if val is not None else "OK(None)"))
        except Exception:
            attempts.append((desc, traceback.format_exc()))
    # Common patterns:
    try_call("bind.Module(data)", lambda: getattr(bind, "Module")(data) if hasattr(bind, "Module") else None)
    for cand in ("ModuleFromMemory","OpenMPTModule","OpenMPT","Mod","Module"):
        try_call(f"bind.{cand}(data)", lambda cand=cand: getattr(bind, cand)(data) if hasattr(bind, cand) else None)
    for cand in ("load_module","load","open_module","from_bytes","create_module","mod_from_bytes"):
        try_call(f"bind.{cand}(data)", lambda cand=cand: getattr(bind, cand)(data) if hasattr(bind, cand) else None)
    try:
        sub = getattr(bind, "openmpt", None)
        if sub:
            try_call("bind.openmpt.Module(data)", lambda: getattr(sub, "Module")(data) if hasattr(sub, "Module") else None)
    except Exception:
        attempts.append(("bind.openmpt.Module", "EXC"))
    try_call("bind.load(data)", lambda: getattr(bind, "load")(data) if hasattr(bind, "load") else None)
    try_call("bind.Module.from_bytes(data)", lambda: getattr(getattr(bind, "Module", None), "from_bytes")(data) if hasattr(bind, "Module") and hasattr(bind.Module, "from_bytes") else None)
    return raw, attempts

def _wrap(raw):
    class ModuleWrapper:
        def __init__(self, raw):
            self._raw = raw
        def _call(self, names):
            for n in names:
                if hasattr(self._raw, n):
                    val = getattr(self._raw, n)
                    try:
                        return val() if callable(val) else val
                    except Exception:
                        continue
            return None
        @property
        def title(self) -> str:
            v = self._call(("title","song_name","get_title","get_song_name","name"))
            return str(v) if v is not None else ""
        @property
        def num_channels(self) -> int:
            v = self._call(("get_num_channels","num_channels","channels","get_channels"))
            try:
                return int(v) if v is not None else 0
            except Exception:
                return 0
        def sample_names(self) -> List[str]:
            names=[]
            try:
                if hasattr(self._raw, "get_num_samples"):
                    n = int(self._raw.get_num_samples())
                    get_name = getattr(self._raw, "get_sample_name", None)
                    for i in range(1,n+1):
                        nm = None
                        if callable(get_name):
                            try: nm = get_name(i)
                            except Exception: nm=None
                        if not nm:
                            try:
                                s = getattr(self._raw, "samples", None)
                                if s and i-1 < len(s):
                                    nm = getattr(s[i-1], "name", None) or getattr(s[i-1], "sample_name", None)
                            except Exception:
                                nm=None
                        names.append(str(nm) if nm else f"sample{i}")
                    return names
            except Exception:
                pass
            try:
                s = getattr(self._raw, "samples", None)
                if s:
                    for i, e in enumerate(s, start=1):
                        nm = getattr(e, "name", None) or getattr(e, "sample_name", None)
                        names.append(str(nm) if nm else f"sample{i}")
                    return names
            except Exception:
                pass
            return names
        def order_list(self):
            v = self._call(("get_order_list","order_list","order","get_order"))
            try:
                return list(v) if v is not None else []
            except Exception:
                return []
        def num_patterns(self):
            v = self._call(("get_num_patterns","num_patterns","patterns_count"))
            try: return int(v) if v is not None else 0
            except Exception: return 0
        def pattern_rows(self, idx):
            try:
                if hasattr(self._raw, "get_pattern"):
                    patt = self._raw.get_pattern(idx)
                    if patt:
                        for a in ("rows","data","pattern"):
                            if hasattr(patt,a):
                                val = getattr(patt,a)
                                try:
                                    return list(val)
                                except Exception:
                                    return [list(r) for r in val]
                pl = getattr(self._raw, "patterns", None)
                if pl and idx < len(pl):
                    p = pl[idx]
                    for a in ("rows","data"):
                        if hasattr(p,a):
                            val=getattr(p,a)
                            try:
                                return list(val)
                            except Exception:
                                return [list(r) for r in val]
            except Exception:
                pass
            ch = max(1, self.num_channels)
            return [["REST"]*ch for _ in range(4)]
    return ModuleWrapper(raw)

def dump_binding_info() -> str:
    if _binding is None:
        return "No binding loaded."
    try:
        attrs = _list_attrs(_binding)
        return f"Binding: {_binding_name}\nTop-level attrs: {', '.join(attrs[:50])}{'...' if len(attrs)>50 else ''}"
    except Exception as e:
        return f"Binding: {_binding_name}\nError listing attrs: {e}"

def load_module_from_bytes(data: bytes):
    if _binding is None:
        raise ImportError("No OpenMPT binding detected. Install 'pyopenmpt' or 'omp4py' in the environment.")
    raw, attempts = _attempt_constructors(_binding, data)
    if raw is None:
        lines = ["Failed constructors:"]
        for desc, res in attempts:
            first = res.splitlines()[0] if isinstance(res,str) and res else str(res)
            lines.append(f" - {desc}: {first}")
        lines.append("Binding info:")
        lines.append(dump_binding_info())
        raise RuntimeError("\n".join(lines))
    try:
        return _wrap(raw)
    except Exception as e:
        raise RuntimeError(f"Module constructed but wrapping failed: {e}\n{dump_binding_info()}")