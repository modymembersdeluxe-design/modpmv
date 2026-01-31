"""
Module-Tracker Adapter (V4-Deluxe update)

This adapter now targets a single (project-specific) binding package named
'module-tracker' (importable as module_tracker or moduletracker). The previous
attempts to detect omp4py / pyopenmpt / openmpt / libopenmpt / pymodopenmpt
have been removed per project request.

The adapter still:
- Tries several constructor patterns that are common across bindings.
- Provides run_diagnostics(data) that prints attempted constructors and binding info.
- Returns a ModuleWrapper with a normalized minimal API:
    - title
    - num_channels
    - sample_names()
    - order_list()
    - num_patterns()
    - pattern_rows(idx)

If you use a different binding package name, install/rename it to 'module-tracker' (or
ensure it is importable as 'module_tracker' or 'moduletracker'), or modify the
_BINDING_CANDIDATES below to match your package name.
"""
from typing import Any, List, Tuple, Optional
import traceback
import io
import os
import tempfile

# Only attempt to import the single new package(s) requested
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

def _attempt_with_bytes(bind, data: bytes) -> Tuple[Optional[Any], List[Tuple[str,str]]]:
    """
    Try a set of commonly used constructor/factory patterns for the module-tracker binding.
    Returns (raw_module_or_None, attempts_list[(desc, trace_or_ok)]).
    """
    attempts = []
    raw = None

    def record(desc, ok, tb):
        attempts.append((desc, "OK" if ok and tb is None else (tb.splitlines()[0] if tb else "OK(None)")))

    # 1) bind.Module(data)
    if hasattr(bind, "Module"):
        ok, tb, val = _safe_call(lambda: getattr(bind, "Module")(data))
        record("bind.Module(data)", ok, tb)
        if ok and val is not None:
            return val, attempts

    # 2) bind.load / bind.load_module / bind.open (bytes, BytesIO)
    for name in ("load", "load_module", "open", "open_module", "from_bytes"):
        if hasattr(bind, name):
            # try BytesIO
            try:
                b = io.BytesIO(data)
                ok, tb, val = _safe_call(lambda name=name, b=b: getattr(bind, name)(b))
                record(f"bind.{name}(BytesIO)", ok, tb)
                if ok and val is not None:
                    return val, attempts
            except Exception:
                record(f"bind.{name}(BytesIO)-exc", False, traceback.format_exc())
            # try writing to a temp file and passing path
            try:
                fd, tmp = tempfile.mkstemp(suffix=".mod")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                ok, tb, val = _safe_call(lambda name=name, tmp=tmp: getattr(bind, name)(tmp))
                record(f"bind.{name}(tmpfile)", ok, tb)
                if ok and val is not None:
                    return val, attempts
            except Exception:
                record(f"bind.{name}(tmpfile)-exc", False, traceback.format_exc())
            finally:
                try:
                    if 'tmp' in locals() and os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass

    # 3) bind.Module.from_bytes / from_buffer if exists
    if hasattr(bind, "Module"):
        M = getattr(bind, "Module")
        for meth in ("from_bytes", "from_buffer", "load"):
            if hasattr(M, meth):
                ok, tb, val = _safe_call(lambda meth=meth: getattr(M, meth)(data))
                record(f"bind.Module.{meth}(data)", ok, tb)
                if ok and val is not None:
                    return val, attempts

    return raw, attempts

def _wrap_module(raw_mod) -> Any:
    """
    Wrap the raw binding module into ModuleWrapper with a stable minimal API.
    """
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
        def title(self) -> str:
            v = self._try(("title","song_name","get_title","get_song_name","name"))
            return str(v) if v is not None else ""

        @property
        def num_channels(self) -> int:
            v = self._try(("get_num_channels","num_channels","channels","get_channels"))
            try:
                return int(v) if v is not None else 0
            except Exception:
                return 0

        def sample_names(self) -> List[str]:
            names = []
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
                    for i, entry in enumerate(s, start=1):
                        nm = getattr(entry, "name", None) or getattr(entry, "sample_name", None)
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

        def pattern_rows(self, idx: int) -> List[List[Any]]:
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

def dump_binding_info() -> str:
    if _binding is None:
        return "No module-tracker binding detected."
    try:
        attrs = _list_attrs(_binding)
        return f"Binding: {_binding_name}\nTop-level attrs (sample): {', '.join(attrs[:80])}{'...' if len(attrs)>80 else ''}"
    except Exception as e:
        return f"Binding: {_binding_name}\nError listing attrs: {e}"

def run_diagnostics(data: Optional[bytes] = None) -> str:
    """
    Run diagnostic constructors and return a report string. If 'data' is provided,
    attempts to create a module using that bytes payload.
    """
    lines = []
    if _binding is None:
        lines.append("No supported 'module-tracker' binding present in environment.")
        lines.append("Attempted import names: " + ", ".join(_BINDING_CANDIDATES))
        return "\n".join(lines)

    lines.append(f"Detected binding: {_binding_name}")
    try:
        attrs = _list_attrs(_binding)
        lines.append("Top-level attrs (partial): " + ", ".join(attrs[:200]) + ("..." if len(attrs) > 200 else ""))
    except Exception as e:
        lines.append(f"Error listing binding attributes: {e}")

    if data is None:
        lines.append("\nNo module bytes supplied. Provide module bytes to run constructor diagnostics.")
        return "\n".join(lines)

    raw, attempts = _attempt_with_bytes(_binding, data)
    lines.append("\nConstructor attempts:")
    for desc, res in attempts:
        lines.append(f"- {desc}: {res}")
    if raw is None:
        lines.append("\nResult: FAILED to construct module object with attempted patterns.")
    else:
        lines.append("\nResult: SUCCESS (constructed raw module) — attempting wrapper introspection...")
        try:
            wrapped = _wrap_module(raw)
            lines.append(f"Wrapped title: {wrapped.title}")
            lines.append(f"Wrapped num_channels: {wrapped.num_channels}")
            try:
                sn = wrapped.sample_names()
                lines.append(f"Wrapped sample_names (count {len(sn)}): {sn[:20]}")
            except Exception:
                lines.append("Wrapped sample_names: <error>")
        except Exception as e:
            lines.append(f"Wrap failed: {e}")
            lines.append("Binding info:\n" + dump_binding_info())

    return "\n".join(lines)

def load_module_from_bytes(data: bytes):
    """
    Construct and return a ModuleWrapper or raise RuntimeError with diagnostics.
    """
    if _binding is None:
        raise ImportError("No module-tracker binding found. Install the package 'module-tracker' (importable as module_tracker or moduletracker) in this environment.")

    raw, attempts = _attempt_with_bytes(_binding, data)
    if raw is None:
        lines = ["Failed to construct module object. Attempts:"]
        for desc, res in attempts:
            lines.append(f"- {desc}: {res}")
        lines.append("Binding info:")
        lines.append(dump_binding_info())
        raise RuntimeError("\n".join(lines))

    try:
        wrapped = _wrap_module(raw)
        return wrapped
    except Exception as e:
        raise RuntimeError(f"Module constructed but wrapper failed: {e}\n{dump_binding_info()}")