"""
Optional helper wrapper for OpenMPT bindings.

This file contains a small helper that attempts to use installed OpenMPT Python bindings
and normalize data into the module_data structure consumed by renderers.

If you install a binding such as `pyopenmpt` or `openmpt`, this wrapper will try to adapt to it.
If the installed binding's API differs from these helper calls, adapt the helper to call the binding's
correct methods (I can help if you paste the binding's Module API).
"""
# This wrapper is intentionally small — the main parse_module_file in mod_parser.py performs similar logic.
# Keep this file as an optional place to put binding-specific code if you prefer.