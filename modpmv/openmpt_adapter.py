"""
OpenMPT adapter with OMP4Py support.

This adapter tries to import several common Python bindings for libopenmpt:
 - pyopenmpt
 - openmpt
 - omp4py
 - libopenmpt

It exposes a single function:
  load_module_from_bytes(data: bytes) -> ModuleWrapper

ModuleWrapper provides a small normalized API used by mod_parser:
 - title (property)
 - num_channels (property)
 - sample_names() -> List[str]
 - order_list() -> List[int]
 - num_patterns() -> int
 - pattern_rows(idx: int) -> List[List[Any]]

The adapter uses defensive attribute checks so it will work with slightly different binding APIs.
If no supported binding is found, load_module_from_bytes will raise ImportError.
"""
from typing import Optional, List, Any
import sys

# Try a sequence of likely binding names; record which one is used for debugging
_binding = None
_binding_name = None
for name in ("pyopenmpt", "openmpt", "omp4py", "libopenmpt", "pymodopenmpt"):
    try:
        mod = __import__(name)
        _binding = mod
        _binding_name = name
        break
    except Exception:
        _binding = None
        _binding_name = None

def _wrap_binding_module(mod_obj) -> Any:
    """
    Wrap the raw binding module object into a ModuleWrapper with the minimal normalized API.
    """
    class ModuleWrapper:
        def __init__(self, raw):
            self._raw = raw

        @property
        def title(self) -> str:
            # try several possible attribute / method names
            for attr in ("title", "song_name", "get_title", "get_song_name"):
                if hasattr(self._raw, attr):
                    val = getattr(self._raw, attr)
                    try:
                        return val() if callable(val) else (val or "")
                    except Exception:
                        continue
            return ""

        @property
        def num_channels(self) -> int:
            for attr in ("get_num_channels", "num_channels", "channels", "get_channels"):
                if hasattr(self._raw, attr):
                    val = getattr(self._raw, attr)
                    try:
                        return int(val()) if callable(val) else int(val)
                    except Exception:
                        continue
            return 0

        def sample_names(self) -> List[str]:
            names = []
            # many bindings expose get_num_samples and get_sample_name / sample_name
            try:
                if hasattr(self._raw, "get_num_samples"):
                    n = int(self._raw.get_num_samples())
                    for i in range(1, n+1):
                        nm = None
                        if hasattr(self._raw, "get_sample_name"):
                            nm = self._raw.get_sample_name(i)
                        elif hasattr(self._raw, "sample_name"):
                            nm = self._raw.sample_name(i)
                        names.append(nm or f"sample{i}")
                    return names
            except Exception:
                pass
            # fallback: try attribute 'samples' if present
            try:
                if hasattr(self._raw, "samples"):
                    s = getattr(self._raw, "samples")
                    for i, item in enumerate(s, start=1):
                        nm = getattr(item, "name", None) or getattr(item, "sample_name", None) or f"sample{i}"
                        names.append(nm)
                    return names
            except Exception:
                pass
            return names

        def order_list(self) -> List[int]:
            for attr in ("get_order_list", "order_list", "order"):
                if hasattr(self._raw, attr):
                    val = getattr(self._raw, attr)
                    try:
                        lst = val() if callable(val) else val
                        return list(lst)
                    except Exception:
                        continue
            return []

        def num_patterns(self) -> int:
            for attr in ("get_num_patterns", "num_patterns", "num_patterns_count"):
                if hasattr(self._raw, attr):
                    val = getattr(self._raw, attr)
                    try:
                        return int(val()) if callable(val) else int(val)
                    except Exception:
                        continue
            return 0

        def pattern_rows(self, idx: int) -> List[List[Any]]:
            """
            Best-effort: attempt to obtain pattern rows for pattern index idx.
            The shape and content of returned rows is binding-dependent. We return a list
            of rows where each row is a list of tokens (raw event objects or simple strings).
            The renderer will try to normalize tokens to "SAMPLE:name" or "REST".
            """
            # Common API: get_pattern -> pattern object with rows attribute
            try:
                if hasattr(self._raw, "get_pattern"):
                    patt = self._raw.get_pattern(idx)
                    if hasattr(patt, "rows"):
                        return list(patt.rows)
                    if hasattr(patt, "data"):
                        return list(patt.data)
            except Exception:
                pass
            # Try pattern_table or patterns attribute
            try:
                if hasattr(self._raw, "patterns"):
                    patt = getattr(self._raw, "patterns")
                    if idx < len(patt):
                        rows = getattr(patt[idx], "rows", None) or getattr(patt[idx], "data", None)
                        if rows:
                            return list(rows)
            except Exception:
                pass
            # Fallback: return a few REST rows
            return [["REST"] * max(1, self.num_channels)]

    return ModuleWrapper(mod_obj)

def load_module_from_bytes(data: bytes):
    """
    Create and return a ModuleWrapper for the provided module bytes.
    If no binding is available, raises ImportError.
    """
    if _binding is None:
        raise ImportError("No OpenMPT binding found. Install a binding such as 'pyopenmpt' or 'omp4py' to enable binary tracker parsing.")

    # Try binding-specific construction patterns
    raw_mod = None
    # 1) pyopenmpt like: pyopenmpt.Module(data)
    try:
        if hasattr(_binding, "Module"):
            raw_mod = _binding.Module(data)
    except Exception:
        raw_mod = None

    # 2) openmpt or custom: binding.open_module / binding.load_module / binding.Mod
    if raw_mod is None:
        for factory in ("open_module", "load_module", "ModuleFromMemory", "Module", "mod_from_bytes"):
            try:
                if hasattr(_binding, factory):
                    fn = getattr(_binding, factory)
                    raw_mod = fn(data) if callable(fn) else None
                    if raw_mod is not None:
                        break
            except Exception:
                raw_mod = None

    # 3) OMP4Py-specific attempt: some bindings might provide a constructor in a submodule
    if raw_mod is None:
        try:
            # Some packages expose a top-level openmpt object or submodule
            sub = getattr(_binding, "openmpt", None)
            if sub and hasattr(sub, "Module"):
                raw_mod = sub.Module(data)
        except Exception:
            raw_mod = None

    if raw_mod is None:
        # last resort: try to call a generic factory name
        try:
            if hasattr(_binding, "load"):
                raw_mod = _binding.load(data)
        except Exception:
            raw_mod = None

    if raw_mod is None:
        raise RuntimeError(f"Binding {_binding_name} found but could not construct module object. Please check the binding API.")

    # Wrap and return normalized module wrapper
    return _wrap_binding_module(raw_mod)