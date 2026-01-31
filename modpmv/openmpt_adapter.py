"""
OpenMPT adapter with improved constructor attempts and diagnostics.

Tries multiple bindings (pyopenmpt, openmpt, omp4py, libopenmpt, pymodopenmpt) and a
variety of constructor/factory call patterns in order to work with differing binding APIs.

If construction fails, the raised RuntimeError contains:
 - binding name discovered
 - attempted constructor patterns and their exception messages
 - a short listing of available attributes on the binding module (to help debugging)

Usage:
    from modpmv.openmpt_adapter import load_module_from_bytes
    modwrap = load_module_from_bytes(bytes_data)
"""
from typing import Optional, List, Any, Tuple
import traceback
import sys

# Candidate binding names to try importing
_BINDING_CANDIDATES = ("pyopenmpt", "openmpt", "omp4py", "libopenmpt", "pymodopenmpt")

_binding = None
_binding_name = None
for name in _BINDING_CANDIDATES:
    try:
        mod = __import__(name)
        _binding = mod
        _binding_name = name
        break
    except Exception:
        _binding = None
        _binding_name = None

def _list_binding_attrs(bind) -> List[str]:
    try:
        return sorted(name for name in dir(bind) if not name.startswith("_"))
    except Exception:
        return []

def _attempt_constructors(bind, data: bytes) -> Tuple[Optional[Any], List[Tuple[str,str]]]:
    """
    Try a list of likely constructor/factory call patterns on the binding.
    Returns (raw_module_or_None, list_of_attempted_results[(desc, exc_text)]).
    """
    attempts = []
    raw = None

    # helper runner
    def try_call(desc, fn):
        nonlocal raw
        if raw is not None:
            return
        try:
            val = fn()
            if val is not None:
                raw = val
            attempts.append((desc, "OK"))
        except Exception as e:
            tb = traceback.format_exc()
            attempts.append((desc, tb))

    # Pattern 1: top-level Module(data)
    try_call("binding.Module(data)", lambda: getattr(bind, "Module")(data) if hasattr(bind, "Module") else None)

    # Pattern 2: top-level constructor with name variations
    for cname in ("ModuleFromMemory", "OpenMPTModule", "OpenMPT", "Mod", "Module"):
        try_call(f"binding.{cname}(data)", lambda cname=cname: getattr(bind, cname)(data) if hasattr(bind, cname) else None)

    # Pattern 3: common factory functions
    for fname in ("load_module", "load", "open_module", "from_bytes", "create_module", "Module.load"):
        try_call(f"binding.{fname}(data)", lambda fname=fname: getattr(bind, fname)(data) if hasattr(bind, fname) else None)

    # Pattern 4: factory functions in submodules (e.g. bind.openmpt.Module)
    try:
        sub = getattr(bind, "openmpt", None)
        if sub:
            try_call("binding.openmpt.Module(data)", lambda: getattr(sub, "Module")(data) if hasattr(sub, "Module") else None)
    except Exception:
        attempts.append(("binding.openmpt.Module(data)", "exception listing openmpt submodule"))

    # Pattern 5: try interpreting binding as a package exposing a 'load' that expects a file-like object
    try_call("binding.load(io.BytesIO(data))", lambda: getattr(bind, "load")(data) if hasattr(bind, "load") else None)

    # Pattern 6: try to call binding.Module.from_bytes or similar
    try_call("binding.Module.from_bytes(data)", lambda: getattr(getattr(bind, "Module", None), "from_bytes")(data) if hasattr(bind, "Module") and hasattr(bind.Module, "from_bytes") else None)

    return raw, attempts

def _wrap_binding_module(raw_mod) -> Any:
    """
    Wrap the raw binding module object into a ModuleWrapper with a minimal normalized API.
    ModuleWrapper implements:
      - title (property)
      - num_channels (property)
      - sample_names() -> List[str]
      - order_list() -> List[int]
      - num_patterns() -> int
      - pattern_rows(idx:int) -> List[List[Any]]
    All accessors try multiple commonly used attribute/method names and degrade gracefully.
    """
    class ModuleWrapper:
        def __init__(self, raw):
            self._raw = raw

        def _try_attrs(self, names):
            for n in names:
                try:
                    if hasattr(self._raw, n):
                        val = getattr(self._raw, n)
                        return val() if callable(val) else val
                except Exception:
                    continue
            return None

        @property
        def title(self) -> str:
            val = self._try_attrs(("title", "song_name", "get_title", "get_song_name", "name"))
            return str(val) if val is not None else ""

        @property
        def num_channels(self) -> int:
            val = self._try_attrs(("get_num_channels", "num_channels", "channels", "get_channels"))
            try:
                return int(val) if val is not None else 0
            except Exception:
                return 0

        def sample_names(self) -> List[str]:
            names = []
            # try explicit API
            try:
                get_num = getattr(self._raw, "get_num_samples", None)
                if callable(get_num):
                    n = int(get_num())
                    get_name = getattr(self._raw, "get_sample_name", None)
                    for i in range(1, n+1):
                        nm = None
                        if callable(get_name):
                            try:
                                nm = get_name(i)
                            except Exception:
                                nm = None
                        if not nm:
                            # attempt attribute access on a samples list
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
            # fallback: iterate raw.samples if present
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

        def order_list(self) -> List[int]:
            val = self._try_attrs(("get_order_list", "order_list", "order", "get_order"))
            try:
                return list(val) if val is not None else []
            except Exception:
                return []

        def num_patterns(self) -> int:
            val = self._try_attrs(("get_num_patterns", "num_patterns", "num_patterns_count", "num_rows", "patterns_count"))
            try:
                return int(val) if val is not None else 0
            except Exception:
                return 0

        def pattern_rows(self, idx: int) -> List[List[Any]]:
            # Try pattern accessors commonly used by bindings
            try:
                # get_pattern(idx) -> pattern object
                if hasattr(self._raw, "get_pattern"):
                    patt = self._raw.get_pattern(idx)
                    if patt is None:
                        return []
                    # patt may have rows or data attributes
                    for attr in ("rows", "data", "pattern"):
                        if hasattr(patt, attr):
                            val = getattr(patt, attr)
                            try:
                                return list(val)
                            except Exception:
                                # try to coerce rows to lists
                                return [list(r) for r in val]
                # fallback: try patterns attribute
                patt_list = getattr(self._raw, "patterns", None)
                if patt_list and idx < len(patt_list):
                    p = patt_list[idx]
                    for attr in ("rows", "data"):
                        if hasattr(p, attr):
                            val = getattr(p, attr)
                            try:
                                return list(val)
                            except Exception:
                                return [list(r) for r in val]
            except Exception:
                pass
            # worst-case: return a few REST rows sized to number of channels
            ch = max(1, self.num_channels)
            return [["REST"] * ch for _ in range(4)]

    return ModuleWrapper(raw_mod)

def dump_binding_info() -> str:
    """Return a diagnostics string with binding name and top-level attrs (helpful when construction fails)."""
    if _binding is None:
        return "No binding loaded."
    info = []
    info.append(f"Binding name: {_binding_name}")
    try:
        attrs = _list_binding_attrs(_binding)
        info.append(f"Top-level attributes ({len(attrs)}): {', '.join(attrs[:50])}" + ("..." if len(attrs) > 50 else ""))
    except Exception as e:
        info.append(f"Error listing attrs: {e}")
    return "\n".join(info)

def load_module_from_bytes(data: bytes):
    """
    Attempt to construct a binding-specific module object and return a normalized ModuleWrapper.
    On failure, raise RuntimeError with detailed diagnostics.
    """
    if _binding is None:
        raise ImportError("No OpenMPT binding found. Install a binding such as 'pyopenmpt' or 'omp4py' to enable binary tracker parsing.")

    raw_mod, attempts = _attempt_constructors(_binding, data)

    if raw_mod is None:
        # Build helpful diagnostics
        msg_lines = []
        msg_lines.append(f"Binding '{_binding_name}' was imported but none of the attempted constructors succeeded.")
        msg_lines.append("Constructor attempts:")
        for desc, result in attempts:
            if result == "OK":
                msg_lines.append(f" - {desc}: OK")
            else:
                # result is traceback string
                first_line = result.splitlines()[0] if result else "<no traceback>"
                msg_lines.append(f" - {desc}: FAILED ({first_line})")
        msg_lines.append("Top-level binding attributes (sample):")
        try:
            attrs = _list_binding_attrs(_binding)
            sample = ", ".join(attrs[:50]) + ("..." if len(attrs) > 50 else "")
            msg_lines.append(sample)
        except Exception as e:
            msg_lines.append(f"Error listing binding attrs: {e}")
        msg = "\n".join(msg_lines)
        raise RuntimeError(msg)

    # wrap raw_mod and return
    try:
        wrapped = _wrap_binding_module(raw_mod)
        return wrapped
    except Exception as e:
        raise RuntimeError(f"Module constructed but wrapping failed: {e}\nBinding debug:\n{dump_binding_info()}")
