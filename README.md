# ModPMV V2

ModPMV V2 — a WIP Python GUI & utilities for automatic generation of YTPMVs (audio + visuals).

High-level features
- .mod-like module parser (text starter + extensible to binary formats)
- Audio renderer: maps tracker samples to audio assets and assembles tracks automatically
- Video renderer: maps tracker events to video samples, images and generative visuals
- Plugin system: Audio / Visual / VisualEffect / LayeredVisual plugins with discovery
- Randomization & automatic generation modes for rapid YTPMV prototyping
- Keyframing and simple graph interpolation API for animated parameters
- Exporter to create a YTPMV-style package (assets + manifest)

Quick start
1. Install dependencies:
   pip install -r requirements.txt
   Ensure ffmpeg is installed and on PATH.
2. Prepare assets:
   - assets/audio_samples/
   - assets/video_samples/
   - assets/images/
3. Run GUI:
   python -m modpmv.gui
4. Load a .mod text file (see examples/), select assets, optional plugins, then Render & Export.

Project layout (key files)
- modpmv/
  - mod_parser.py
  - assets.py
  - audio_renderer.py
  - video_renderer.py
  - plugins/
    - base.py
    - loader.py
  - ytpmv_exporter.py
  - gui.py
- examples/
  - plugins/ (example plugins)
  - examples.mod (sample mod text)
- README.md, TUTORIAL-ModPMV.md, requirements.txt, pyproject.toml

Notes
- The included parsers/renderers are intentionally prototyping-grade. For production, replace the parser with an accurate binary .mod parser (ProTracker/IT/XM) or provide a converter.
- MoviePy is convenient but can be slow for long HD renders. Consider ffmpeg frame pipelines for heavy workloads.
- Plugin authors: use tags and metadata to make your plugin discoverable in the GUI.

If you want, I can:
- Add a JSON config editor to the GUI for plugin config
- Add a preview/thumbnail generator and cache
- Implement a waveform visual plugin and a beat-slicer audio plugin as examples