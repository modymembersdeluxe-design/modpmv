"""
OpenMPT adapter (improved diagnostics & constructor attempts).

This adapter tries many constructor/factory patterns to work with differing
Python wrappers for libopenmpt (pyopenmpt, omp4py, openmpt, libopenmpt, etc.).

If it cannot construct a module object it raises a RuntimeError containing:
 - attempted constructors and their short tracebacks
 - a sample of top-level attributes on the binding
 - (if provided bytes) attempts using a temporary file

Functions:
 - load_module_from_bytes(data: bytes) -> ModuleWrapper
 - dump_binding_info() -> str
 - run_diagnostics(data: Optional[bytes] = None) -> str

If you run run_diagnostics with the module bytes and paste the output here I will
extend the adapter to support that binding exactly.
"""
from typing import Any, List, Tuple, Optional
import traceback
import tempfile
import io
import os

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

def _safe_call(fn_desc: str, fn):
    try:
        val = fn()
        return (True, None, val)
    except Exception as e:
        tb = traceback.format_exc()
        return (False, tb, None)

def _attempt_with_bytes(bind, data: bytes) -> Tuple[Optional[Any], List[Tuple[str,str]]]:
    """
    Attempt many constructor patterns that might accept raw bytes or file-like objects.
    Returns (raw_module_or_None, attempts_list[(desc, trace_or_ok)])
    """
    attempts = []
    raw = None

    def record(desc, ok, tb):
        attempts.append((desc, "OK" if ok else (tb.splitlines()[0] if tb else "EXC")))

    # 1) Common top-level constructors
    candidates = [
        ("bind.Module(data)", lambda: getattr(bind, "Module")(data) if hasattr(bind, "Module") else None),
        ("bind.ModuleFromMemory(data)", lambda: getattr(bind, "ModuleFromMemory")(data) if hasattr(bind, "ModuleFromMemory") else None),
        ("bind.OpenMPTModule(data)", lambda: getattr(bind, "OpenMPTModule")(data) if hasattr(bind, "OpenMPTModule") else None),
        ("bind.Mod(data)", lambda: getattr(bind, "Mod")(data) if hasattr(bind, "Mod") else None),
        ("bind.load_module(data)", lambda: getattr(bind, "load_module")(data) if hasattr(bind, "load_module") else None),
        ("bind.load(data)", lambda: getattr(bind, "load")(data) if hasattr(bind, "load") else None),
        ("bind.open_module(data)", lambda: getattr(bind, "open_module")(data) if hasattr(bind, "open_module") else None),
        ("bind.from_bytes(data)", lambda: getattr(bind, "from_bytes")(data) if hasattr(bind, "from_bytes") else None),
    ]
    for desc, fn in candidates:
        ok, tb, val = _safe_call(desc, fn)
        record(desc, ok, tb)
        if ok and val is not None:
            raw = val
            break

    if raw is not None:
        return raw, attempts

    # 2) Try factory on bind.Module (from_bytes, from_buffer, from_file)
    if hasattr(bind, "Module"):
        M = getattr(bind, "Module")
        sub_candidates = [
            ("bind.Module.from_bytes(data)", lambda: getattr(M, "from_bytes")(data) if hasattr(M, "from_bytes") else None),
            ("bind.Module.from_buffer(data)", lambda: getattr(M, "from_buffer")(data) if hasattr(M, "from_buffer") else None),
            ("bind.Module.load(data)", lambda: getattr(M, "load")(data) if hasattr(M, "load") else None),
        ]
        for desc, fn in sub_candidates:
            ok, tb, val = _safe_call(desc, fn)
            record(desc, ok, tb)
            if ok and val is not None:
                raw = val
                break
    if raw is not None:
        return raw, attempts

    # 3) Try passing a file-like object (io.BytesIO)
    try:
        bobj = io.BytesIO(data)
        filelike_candidates = [
            ("bind.load(BytesIO)", lambda: getattr(bind, "load")(bobj) if hasattr(bind, "load") else None),
            ("bind.open_module(BytesIO)", lambda: getattr(bind, "open_module")(bobj) if hasattr(bind, "open_module") else None),
        ]
        for desc, fn in filelike_candidates:
            ok, tb, val = _safe_call(desc, fn)
            record(desc, ok, tb)
            if ok and val is not None:
                raw = val
                break
    except Exception as e:
        attempts.append(("BytesIO attempt", traceback.format_exc()))

    if raw is not None:
        return raw, attempts

    # 4) Some bindings require a filename. Write to temp file and try filename-based factories.
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".mod")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        file_candidates = [
            ("bind.load_module(file_path)", lambda: getattr(bind, "load_module")(tmp_path) if hasattr(bind, "load_module") else None),
            ("bind.load(file_path)", lambda: getattr(bind, "load")(tmp_path) if hasattr(bind, "load") else None),
            ("bind.open_module(file_path)", lambda: getattr(bind, "open_module")(tmp_path) if hasattr(bind, "open_module") else None),
            ("bind.Module(tmp_path)", lambda: getattr(bind, "Module")(tmp_path) if hasattr(bind, "Module") else None),
        ]
        for desc, fn in file_candidates:
            ok, tb, val = _safe_call(desc, fn)
            record(desc, ok, tb)
            if ok and val is not None:
                raw = val
                break
    except Exception as e:
        attempts.append(("file-path attempt", traceback.format_exc()))
    finally:
        # keep the temp file for debugging if no success (do not delete here if raw is None)
        if raw is None and tmp_path and os.path.exists(tmp_path):
            # leave file for user to inspect; caller/diagnostic will report its path
            attempts.append(("tempfile_left_for_debug", tmp_path))
        else:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    return raw, attempts

def _wrap_module(raw_mod) -> Any:
    """
    Wrap the raw module object into a simple ModuleWrapper with:
     - title
     - num_channels
     - sample_names()
     - order_list()
     - num_patterns()
     - pattern_rows(idx)
    The wrapper tries multiple attribute/method names defensively.
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
                    for i, e in enumerate(s, start=1):
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

        def pattern_rows(self, idx: int) -> List[List[Any]]:
            try:
                if hasattr(self._raw, "get_pattern"):
                    patt = self._raw.get_pattern(idx)
                    if patt:
                        for a in ("rows", "data", "pattern"):
                            if hasattr(patt, a):
                                val = getattr(patt, a)
                                try:
                                    return list(val)
                                except Exception:
                                    return [list(r) for r in val]
                pl = getattr(self._raw, "patterns", None)
                if pl and idx < len(pl):
                    p = pl[idx]
                    for a in ("rows", "data"):
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
        return "No binding loaded."
    try:
        attrs = _list_attrs(_binding)
        return f"Binding: {_binding_name}\nTop-level attributes (sample): {', '.join(attrs[:50])}{'...' if len(attrs)>50 else ''}"
    except Exception as e:
        return f"Binding: {_binding_name}\nError listing attrs: {e}"

def run_diagnostics(data: Optional[bytes] = None) -> str:
    """
    Run constructor attempts and return a detailed diagnostic string.
    If 'data' is provided, it will attempt constructors using that data; otherwise only binding info is shown.
    """
    lines = []
    if _binding is None:
        lines.append("No known OpenMPT binding found in this environment.")
        lines.append("Tried candidates: " + ", ".join(_BINDING_CANDIDATES))
        return "\n".join(lines)

    lines.append(f"Detected binding: {_binding_name}")
    lines.append("Top-level attributes (sample):")
    try:
        attrs = _list_attrs(_binding)
        lines.append(", ".join(attrs[:200]) + ("..." if len(attrs) > 200 else ""))
    except Exception as e:
        lines.append(f"Error listing attributes: {e}")

    if data is None:
        lines.append("\nNo data supplied to constructor diagnostics. To run full diagnostics, call run_diagnostics(data) with module bytes.")
        return "\n".join(lines)

    raw, attempts = _attempt_with_bytes(_binding, data)
    lines.append("\nConstructor attempts:")
    for desc, res in attempts:
        lines.append(f"- {desc}: {res}")
    if raw is None:
        lines.append("\nResult: FAILED to construct module object with attempted patterns.")
        lines.append("If possible, provide the output of this diagnostic and a small sample module file for me to adapt the adapter.")
    else:
        lines.append("\nResult: SUCCESS (constructed a raw module object). Attempting to wrap...")
        try:
            wrapped = _wrap_module(raw)
            # call a few introspection methods (safe)
            try:
                lines.append(f"Wrapped title: {wrapped.title}")
            except Exception:
                lines.append("Wrapped title: <error>")
            try:
                lines.append(f"Wrapped num_channels: {wrapped.num_channels}")
            except Exception:
                lines.append("Wrapped num_channels: <error>")
            try:
                names = wrapped.sample_names()
                lines.append(f"Wrapped sample_names (count {len(names)}): {names[:20]}")
            except Exception:
                lines.append("Wrapped sample_names: <error>")
        except Exception as e:
            lines.append(f"Wrapping failed: {e}")
            lines.append("Binding info dump:")
            lines.append(dump_binding_info())
    return "\n".join(lines)

def load_module_from_bytes(data: bytes):
    """
    Public loader: returns a ModuleWrapper or raises RuntimeError with diagnostics.
    """
    if _binding is None:
        raise ImportError("No OpenMPT binding detected. Install 'pyopenmpt' or 'omp4py' in the active environment.")
    raw, attempts = _attempt_with_bytes(_binding, data)
    if raw is None:
        lines = ["Failed to construct module with tried constructors:"]
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