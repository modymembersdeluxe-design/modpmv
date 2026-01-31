"""
Module-Tracker Adapter — extended support for 'module_tracker' binding

This file extends the adapter to handle a binding that exposes top-level
names like `tracker`, `analyzer`, or `track_glob`. It will try binding-
specific constructor patterns (including functions that accept bytes or a
file path), then fall back to the generic attempts. If construction still
fails the adapter will raise a RuntimeError with a diagnostic summary.

Usage:
    from modpmv.openmpt_adapter import load_module_from_bytes, run_diagnostics
"""
from typing import Any, List, Tuple, Optional
import traceback
import io
import os
import tempfile

# Only the single project-adopted package names are attempted
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

def _try_module_tracker_patterns(bind, data: bytes):
    """
    Try constructor patterns specific to 'module_tracker' binding (observed names:
    tracker, analyzer, track_glob). Returns (raw_mod_or_None, attempts_list).
    """
    attempts = []
    raw = None

    def rec(desc, ok, tb):
        attempts.append((desc, "OK" if ok and tb is None else (tb.splitlines()[0] if tb else "OK(None)")))

    # If bind.tracker exists and is callable, try common ways to call it
    if hasattr(bind, "tracker") and callable(getattr(bind, "tracker")):
        # try passing raw bytes
        ok, tb, val = _safe_call(lambda: getattr(bind, "tracker")(data))
        rec("module_tracker.tracker(bytes)", ok, tb)
        if ok and val is not None:
            return val, attempts
        # try BytesIO wrapper
        try:
            b = io.BytesIO(data)
            ok, tb, val = _safe_call(lambda: getattr(bind, "tracker")(b))
            rec("module_tracker.tracker(BytesIO)", ok, tb)
            if ok and val is not None:
                return val, attempts
        except Exception:
            rec("module_tracker.tracker(BytesIO)-exc", False, traceback.format_exc())
        # try writing to temp file and passing path (some bindings expect filename)
        try:
            fd, tmp = tempfile.mkstemp(suffix=".mod")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            ok, tb, val = _safe_call(lambda: getattr(bind, "tracker")(tmp))
            rec("module_tracker.tracker(tempfile path)", ok, tb)
            if ok and val is not None:
                return val, attempts
        except Exception:
            rec("module_tracker.tracker(tempfile)-exc", False, traceback.format_exc())
        finally:
            try:
                if 'tmp' in locals() and os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    # Try analyzer(...) if present
    if hasattr(bind, "analyzer") and callable(getattr(bind, "analyzer")):
        ok, tb, val = _safe_call(lambda: getattr(bind, "analyzer")(data))
        rec("module_tracker.analyzer(bytes)", ok, tb)
        if ok and val is not None:
            return val, attempts
        try:
            b = io.BytesIO(data)
            ok, tb, val = _safe_call(lambda: getattr(bind, "analyzer")(b))
            rec("module_tracker.analyzer(BytesIO)", ok, tb)
            if ok and val is not None:
                return val, attempts
        except Exception:
            rec("module_tracker.analyzer(BytesIO)-exc", False, traceback.format_exc())

    # Try track_glob or other helpers that might return an object when given path
    if hasattr(bind, "track_glob") and callable(getattr(bind, "track_glob")):
        # try writing file and calling track_glob on its directory
        try:
            fd, tmp = tempfile.mkstemp(suffix=".mod")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            dirpath = os.path.dirname(tmp)
            ok, tb, val = _safe_call(lambda: getattr(bind, "track_glob")(dirpath))
            rec("module_tracker.track_glob(tmpdir)", ok, tb)
            if ok and val is not None:
                return val, attempts
        except Exception:
            rec("module_tracker.track_glob(tmpdir)-exc", False, traceback.format_exc())
        finally:
            try:
                if 'tmp' in locals() and os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    return None, attempts

def _attempt_generic(bind, data: bytes):
    """
    Generic constructor attempts across bindings: Module(data), load(BytesIO), Module.from_bytes, etc.
    """
    attempts = []
    raw = None

    def rec(desc, ok, tb):
        attempts.append((desc, "OK" if ok and tb is None else (tb.splitlines()[0] if tb else "OK(None)")))

    # Module(data)
    if hasattr(bind, "Module"):
        ok, tb, val = _safe_call(lambda: getattr(bind, "Module")(data))
        rec("bind.Module(data)", ok, tb)
        if ok and val is not None:
            return val, attempts

    # Module.from_bytes / from_buffer
    if hasattr(bind, "Module"):
        M = getattr(bind, "Module")
        for meth in ("from_bytes", "from_buffer", "load"):
            if hasattr(M, meth):
                ok, tb, val = _safe_call(lambda meth=meth: getattr(M, meth)(data))
                rec(f"bind.Module.{meth}(data)", ok, tb)
                if ok and val is not None:
                    return val, attempts

    # top-level loaders: load/open/load_module/open_module/from_bytes
    for name in ("load", "open", "load_module", "open_module", "from_bytes"):
        if hasattr(bind, name):
            # try BytesIO
            try:
                b = io.BytesIO(data)
                ok, tb, val = _safe_call(lambda name=name, b=b: getattr(bind, name)(b))
                rec(f"bind.{name}(BytesIO)", ok, tb)
                if ok and val is not None:
                    return val, attempts
            except Exception:
                rec(f"bind.{name}(BytesIO)-exc", False, traceback.format_exc())
            # try tmpfile path
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

    # last resort: bind.load(data) raw
    if hasattr(bind, "load"):
        ok, tb, val = _safe_call(lambda: getattr(bind, "load")(data))
        rec("bind.load(data)", ok, tb)
        if ok and val is not None:
            return val, attempts

    return None, attempts

def _wrap_module(raw_mod) -> Any:
    """
    Wrap the raw module object into a ModuleWrapper that exposes a small uniform API.
    Defensive attribute/method probing is used for library differences.
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
            v = self._try(("title", "song_name", "get_title", "get_song_name", "name"))
            return str(v) if v is not None else ""

        @property
        def num_channels(self) -> int:
            v = self._try(("get_num_channels", "num_channels", "channels", "get_channels"))
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
                    for i in range(1, n + 1):
                        nm = None
                        if callable(get_name):
                            try:
                                nm = get_name(i)
                            except Exception:
                                nm = None
                        if not nm:
                            try:
                                s = getattr(self._raw, "samples", None)
                                if s and i - 1 < len(s):
                                    nm = getattr(s[i - 1], "name", None) or getattr(s[i - 1], "sample_name", None)
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
            v = self._try(("get_order_list", "order_list", "order", "get_order"))
            try:
                return list(v) if v is not None else []
            except Exception:
                return []

        def num_patterns(self):
            v = self._try(("get_num_patterns", "num_patterns", "patterns_count"))
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
        return "No binding detected."
    try:
        attrs = _list_attrs(_binding)
        return f"Binding: {_binding_name}\nTop-level attrs (sample): {', '.join(attrs[:80])}{'...' if len(attrs)>80 else ''}"
    except Exception as e:
        return f"Binding: {_binding_name}\nError listing attrs: {e}"

def run_diagnostics(data: Optional[bytes] = None) -> str:
    """
    Produce a diagnostic report. If data (module bytes) is provided, attempt constructors.
    """
    lines = []
    if _binding is None:
        lines.append("No 'module-tracker' binding found in environment.")
        lines.append("Tried names: " + ", ".join(_BINDING_CANDIDATES))
        return "\n".join(lines)

    lines.append(f"Detected binding: {_binding_name}")
    try:
        attrs = _list_attrs(_binding)
        lines.append("Top-level attrs (partial): " + ", ".join(attrs[:200]) + ("..." if len(attrs) > 200 else ""))
    except Exception as e:
        lines.append(f"Error listing attributes: {e}")

    if data is None:
        lines.append("\nNo module bytes supplied; call run_diagnostics(data) with module bytes to run constructor attempts.")
        return "\n".join(lines)

    raw, attempts = _try_module_tracker_patterns(_binding, data)
    if raw is not None:
        lines.append("\nBinding-specific constructor: SUCCESS")
        try:
            wrapped = _wrap_module(raw)
            lines.append(f"Wrapped title: {wrapped.title}")
            lines.append(f"Wrapped num_channels: {wrapped.num_channels}")
        except Exception as e:
            lines.append(f"Wrap after success failed: {e}")
        lines.extend([f"- {d}: {r}" for d, r in attempts])
        return "\n".join(lines)

    raw2, attempts2 = _attempt_generic(_binding, data)
    attempts_all = attempts + attempts2
    lines.append("\nConstructor attempts (binding-specific then generic):")
    for desc, res in attempts_all:
        lines.append(f"- {desc}: {res}")
    if raw2 is None:
        lines.append("\nResult: FAILED to construct module object with attempted patterns.")
    else:
        lines.append("\nGeneric constructor: SUCCESS (wrapped introspection)")
        try:
            wrapped = _wrap_module(raw2)
            lines.append(f"Wrapped title: {wrapped.title}")
            lines.append(f"Wrapped num_channels: {wrapped.num_channels}")
        except Exception as e:
            lines.append(f"Wrap failed after generic construction: {e}")
            lines.append("Binding dump:\n" + dump_binding_info())
    return "\n".join(lines)

def load_module_from_bytes(data: bytes):
    """
    Public loader: returns ModuleWrapper or raises RuntimeError with diagnostic info.
    """
    if _binding is None:
        raise ImportError("No 'module-tracker' binding found. Install the 'module-tracker' package (importable as module_tracker or moduletracker).")

    raw, attempts = _try_module_tracker_patterns(_binding, data)
    if raw is None:
        raw, attempts2 = _attempt_generic(_binding, data)
        attempts.extend(attempts2 or [])

    if raw is None:
        lines = ["Failed to construct module object. Attempts summary:"]
        lines.extend([f"- {d}: {r}" for d, r in attempts])
        lines.append("Binding info:")
        lines.append(dump_binding_info())
        raise RuntimeError("\n".join(lines))

    try:
        wrapped = _wrap_module(raw)
        return wrapped
    except Exception as e:
        raise RuntimeError(f"Module constructed but wrapper failed: {e}\n{dump_binding_info()}")