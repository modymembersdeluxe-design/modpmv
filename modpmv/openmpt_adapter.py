"""
Module-Tracker Adapter — tolerant diagnostics (safe to call from parser).

This adapter still tries to build a ModuleWrapper for a binding named
'module_tracker' or 'moduletracker' if one is installed, and exposes:

- load_module_from_bytes(data: bytes) -> ModuleWrapper
- run_diagnostics(data: Optional[bytes]) -> str

Note: load_module_from_bytes may still raise on unrecoverable errors;
the parser wraps calls and falls back safely. run_diagnostics returns a
copy-pastable diagnostic string you can use for debugging.
"""
from typing import Any, List, Tuple, Optional
import traceback
import io
import os
import tempfile

_BINDING_CANDIDATES = ("module_tracker", "moduletracker")

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

def _safe_call(fn):
    try:
        return (True, None, fn())
    except Exception:
        return (False, traceback.format_exc(), None)

def _attempt_with_bytes(bind, data: bytes):
    attempts = []
    raw = None
    def rec(desc, ok, tb):
        attempts.append((desc, "OK" if ok and tb is None else (tb.splitlines()[0] if tb else "OK(None)")))
    # Try a few patterns (binding-specific then generic)
    if hasattr(bind, "tracker") and callable(getattr(bind, "tracker")):
        ok, tb, val = _safe_call(lambda: getattr(bind, "tracker")(data))
        rec("bind.tracker(data)", ok, tb)
        if ok and val is not None:
            return val, attempts
        try:
            b = io.BytesIO(data)
            ok, tb, val = _safe_call(lambda: getattr(bind, "tracker")(b))
            rec("bind.tracker(BytesIO)", ok, tb)
            if ok and val is not None:
                return val, attempts
        except Exception:
            rec("bind.tracker(BytesIO)-exc", False, traceback.format_exc())
        # try tempfile path
        try:
            fd, tmp = tempfile.mkstemp(suffix=".mod")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            ok, tb, val = _safe_call(lambda: getattr(bind, "tracker")(tmp))
            rec("bind.tracker(tmpfile)", ok, tb)
            if ok and val is not None:
                return val, attempts
        except Exception:
            rec("bind.tracker(tmpfile)-exc", False, traceback.format_exc())
        finally:
            try:
                if 'tmp' in locals() and os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    # try analyzer if present
    if hasattr(bind, "analyzer") and callable(getattr(bind, "analyzer")):
        ok, tb, val = _safe_call(lambda: getattr(bind, "analyzer")(data))
        rec("bind.analyzer(data)", ok, tb)
        if ok and val is not None:
            return val, attempts
        try:
            b = io.BytesIO(data)
            ok, tb, val = _safe_call(lambda: getattr(bind, "analyzer")(b))
            rec("bind.analyzer(BytesIO)", ok, tb)
            if ok and val is not None:
                return val, attempts
        except Exception:
            rec("bind.analyzer(BytesIO)-exc", False, traceback.format_exc())

    # generic attempts
    for name in ("Module", "load", "load_module", "open", "open_module", "from_bytes"):
        if hasattr(bind, name):
            # try bytes
            try:
                ok, tb, val = _safe_call(lambda name=name: getattr(bind, name)(data))
                rec(f"bind.{name}(data)", ok, tb)
                if ok and val is not None:
                    return val, attempts
            except Exception:
                rec(f"bind.{name}(data)-exc", False, traceback.format_exc())
            # try BytesIO
            try:
                b = io.BytesIO(data)
                ok, tb, val = _safe_call(lambda name=name, b=b: getattr(bind, name)(b))
                rec(f"bind.{name}(BytesIO)", ok, tb)
                if ok and val is not None:
                    return val, attempts
            except Exception:
                rec(f"bind.{name}(BytesIO)-exc", False, traceback.format_exc())
            # try tmpfile
            try:
                fd, tmp = tempfile.mkstemp(suffix=".mod")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                ok, tb, val = _safe_call(lambda name=name, tmp=tmp: getattr(bind, name)(tmp))
                rec(f"bind.{name}(tmpfile)", ok, tb)
                if ok and val is not None:
                    return val, attempts
            except Exception:
                rec(f"bind.{name}(tmpfile)-exc", False, traceback.format_exc())
            finally:
                try:
                    if 'tmp' in locals() and os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass

    return None, attempts

def _wrap_module(raw_mod):
    class ModuleWrapper:
        def __init__(self, raw):
            self._raw = raw
        def _try(self, names):
            for n in names:
                try:
                    if hasattr(self._raw, n):
                        v = getattr(self._raw, n)
                        return v() if callable(v) else v
                except Exception:
                    continue
            return None
        @property
        def title(self):
            v = self._try(("title","song_name","get_title","get_song_name","name"))
            return str(v) if v is not None else ""
        @property
        def num_channels(self):
            v = self._try(("get_num_channels","num_channels","channels","get_channels"))
            try:
                return int(v) if v is not None else 0
            except Exception:
                return 0
        def sample_names(self):
            names=[]
            try:
                if hasattr(self._raw, "get_num_samples") and callable(getattr(self._raw, "get_num_samples")):
                    n = int(self._raw.get_num_samples())
                    get_name = getattr(self._raw, "get_sample_name", None)
                    for i in range(1, n+1):
                        nm = None
                        if callable(get_name):
                            try:
                                nm = get_name(i)
                            except Exception:
                                nm = None
                        if not nm:
                            try:
                                s = getattr(self._raw, "samples", None)
                                if s and i-1 < len(s):
                                    nm = getattr(s[i-1], "name", None) or getattr(s[i-1], "sample_name", None)
                            except Exception:
                                nm = None
                        names.append(str(nm) if nm else f"sample{i}")
                    return names
            except Exception:
                pass
            try:
                s = getattr(self._raw, "samples", None)
                if s:
                    for i,e in enumerate(s, start=1):
                        nm = getattr(e, "name", None) or getattr(e, "sample_name", None)
                        names.append(str(nm) if nm else f"sample{i}")
                    return names
            except Exception:
                pass
            return names
        def order_list(self):
            v = self._try(("get_order_list","order_list","order","get_order"))
            try:
                return list(v) if v is not None else []
            except Exception:
                return []
        def num_patterns(self):
            v = self._try(("get_num_patterns","num_patterns","patterns_count"))
            try:
                return int(v) if v is not None else 0
            except Exception:
                return 0
        def pattern_rows(self, idx):
            try:
                if hasattr(self._raw, "get_pattern"):
                    patt = self._raw.get_pattern(idx)
                    if patt:
                        for a in ("rows","data","pattern"):
                            if hasattr(patt, a):
                                val = getattr(patt, a)
                                try:
                                    return list(val)
                                except Exception:
                                    return [list(r) for r in val]
                pl = getattr(self._raw, "patterns", None)
                if pl and idx < len(pl):
                    p = pl[idx]
                    for a in ("rows","data"):
                        if hasattr(p, a):
                            val = getattr(p, a)
                            try:
                                return list(val)
                            except Exception:
                                return [list(r) for r in val]
            except Exception:
                pass
            ch = max(1, self.num_channels)
            return [["REST"] * ch for _ in range(4)]
    return ModuleWrapper(raw_mod)

def dump_binding_info():
    if _binding is None:
        return "No binding detected."
    try:
        attrs = _list_attrs(_binding)
        return f"Binding: {_binding_name}\nTop-level attrs (sample): {', '.join(attrs[:80])}{'...' if len(attrs)>80 else ''}"
    except Exception as e:
        return f"Binding: {_binding_name}\nError listing attrs: {e}"

def run_diagnostics(data: Optional[bytes] = None):
    lines=[]
    if _binding is None:
        lines.append("No binding present (module_tracker).")
        return "\n".join(lines)
    lines.append(f"Detected binding: {_binding_name}")
    try:
        attrs = _list_attrs(_binding)
        lines.append("Top-level attrs (partial): " + ", ".join(attrs[:200]) + ("..." if len(attrs)>200 else ""))
    except Exception as e:
        lines.append(f"Error listing attrs: {e}")
    if data is None:
        lines.append("\nNo data provided for constructor diagnostics.")
        return "\n".join(lines)
    raw, attempts = _attempt_with_bytes(_binding, data)
    lines.append("\nConstructor attempts:")
    for desc,res in attempts:
        lines.append(f"- {desc}: {res}")
    if raw is None:
        lines.append("\nResult: FAILED to construct module object.")
    else:
        lines.append("\nResult: SUCCESS — wrapping module")
        try:
            wrapped = _wrap_module(raw)
            lines.append(f"Wrapped title: {wrapped.title}")
            lines.append(f"Wrapped num_channels: {wrapped.num_channels}")
        except Exception as e:
            lines.append(f"Wrap failed: {e}")
    return "\n".join(lines)

def load_module_from_bytes(data: bytes):
    if _binding is None:
        raise ImportError("No module_tracker binding installed.")
    raw, attempts = _attempt_with_bytes(_binding, data)
    if raw is None:
        lines=["Failed to construct module object. Attempts:"]
        for d,r in attempts:
            lines.append(f"- {d}: {r}")
        lines.append("Binding info:")
        lines.append(dump_binding_info())
        raise RuntimeError("\n".join(lines))
    try:
        return _wrap_module(raw)
    except Exception as e:
        raise RuntimeError(f"Module constructed but wrapper failed: {e}\n{dump_binding_info()}")