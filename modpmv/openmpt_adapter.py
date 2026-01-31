"""
OpenMPT adapter: attempt to normalize different Python bindings for libopenmpt.

Notes:
- There are several Python wrappers for libopenmpt. This adapter attempts to provide a small, stable facade:
    - load_module(data: bytes) -> ModuleWrapper
    - ModuleWrapper exposes:
        - title, num_channels, num_patterns, order_list, pattern_rows(pattern_index) -> list(rows)
        - sample_names() -> list[str]
- If the exact binding API differs we adapt; paste your binding's Module API and I will refine this adapter.
"""
from typing import Optional, List, Any
import os

# Try to import common binding names
_binding = None
for name in ("pyopenmpt", "openmpt", "libopenmpt", "pymodopenmpt"):
    try:
        _binding = __import__(name)
        break
    except Exception:
        _binding = None

if _binding is None:
    # adapter will raise ImportError when used
    def load_module_from_bytes(data: bytes):
        raise ImportError("No OpenMPT binding available. Install 'pyopenmpt' or a compatible package.")
else:
    def load_module_from_bytes(data: bytes):
        """
        Construct a wrapper around the binding's module object.
        This wrapper provides a minimal normalized API for ModPMV renderers.
        """
        # Example for pyopenmpt.Module(data)
        try:
            if hasattr(_binding, "Module"):
                mod = _binding.Module(data)
            elif hasattr(_binding, "OpenMPTModule"):
                mod = _binding.OpenMPTModule(data)
            else:
                # try common factory
                mod = _binding.load_module(data)
        except Exception as e:
            raise RuntimeError(f"Failed to create module from binding: {e}")

        class ModuleWrapper:
            def __init__(self, mod):
                self._mod = mod
            @property
            def title(self) -> str:
                return getattr(self._mod, "title", "") or getattr(self._mod, "song_name", "") or "untitled"
            @property
            def num_channels(self) -> int:
                try:
                    return int(getattr(self._mod, "get_num_channels", lambda: 0)() or getattr(self._mod, "num_channels", 0) or 0)
                except Exception:
                    return 0
            def sample_names(self) -> List[str]:
                names = []
                try:
                    get_num = getattr(self._mod, "get_num_samples", None)
                    if callable(get_num):
                        n = int(get_num())
                        for i in range(1, n+1):
                            nm = getattr(self._mod, "get_sample_name", lambda idx: f"sample{idx}")(i) or f"sample{i}"
                            names.append(nm)
                except Exception:
                    # fallback: return empty
                    pass
                return names
            def order_list(self) -> List[int]:
                try:
                    # try several possible names
                    if hasattr(self._mod, "get_order_list"):
                        return list(self._mod.get_order_list())
                    if hasattr(self._mod, "order_list"):
                        return list(self._mod.order_list)
                    if hasattr(self._mod, "order"):
                        return list(self._mod.order)
                except Exception:
                    pass
                return []
            def num_patterns(self) -> int:
                try:
                    return int(getattr(self._mod, "get_num_patterns", lambda: 0)() or getattr(self._mod, "num_patterns", 0) or 0)
                except Exception:
                    return 0
            def pattern_rows(self, idx: int) -> List[List[Any]]:
                """
                Return pattern rows; best-effort. The inner structure of rows/entries depends on the binding.
                We return a list of rows, where each row is a list of token-like objects (raw).
                Renderer will attempt to normalize tokens to "SAMPLE:name" or "REST".
                """
                # Many bindings do not provide a high-level pattern API; attempt safe fallbacks
                try:
                    if hasattr(self._mod, "get_pattern"):
                        patt = self._mod.get_pattern(idx)
                        if hasattr(patt, "rows"):
                            return list(patt.rows)
                        if hasattr(patt, "data"):
                            return list(patt.data)
                except Exception:
                    pass
                # fallback: return a few empty rows
                return [["REST"]] * 4

        return ModuleWrapper(mod)