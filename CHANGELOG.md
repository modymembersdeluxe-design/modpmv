# ModPMV Changelog

## v0.3.0 → v0.3.0 (V3)
- New: OpenMPT adapter added — supports .it/.xm/.mod parsing if binding installed
- New: per-channel (1–32) pattern mapping to visual layers
- New: plugin manifest + preview + config editor in GUI
- New: caching subsystem for previews and intermediate audio
- New: ffmpeg pipeline stub for future optimized rendering
- Updated: GUI imports now try PyQt6/PySide6/PyQt5/PySide2 in order, improving Windows compatibility
- Updated: YTPMV exporter writes precise manifest and copies only used clips (best-effort)
- Docs: README, tutorial and Windows guide updated

(See docs/TUTORIAL-ModPMV.md for Pro usage and performance tips)