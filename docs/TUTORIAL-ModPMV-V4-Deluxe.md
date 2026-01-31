# ModPMV V4 Deluxe — Full Tutorial

This tutorial explains how to get started with ModPMV V4 Deluxe, covers installation, GUI and CLI workflows, plugin authoring, OpenMPT binding setup (including omp4py), rendering modes (moviepy / ffmpeg), previewing and packaging YTPMV exports, troubleshooting, and recommended production practices.

Contents
- Quick prerequisites
- Installation (Windows / macOS / Linux)
- Project layout recap
- First run — GUI quickstart
- Headless run — CLI quickstart
- Rendering modes: moviepy vs ffmpeg
- OpenMPT bindings (binary modules .it/.xm/.mod)
- Plugin system: types, discovery, examples
- Preview, caching & deterministic runs
- Render queue & background worker
- Packaging YTPMV output
- Troubleshooting & common fixes
- Tips for performance & production
- Next steps and resources

---

Quick prerequisites
- Python 3.9+ (64-bit recommended)
- FFmpeg binary on PATH (or imageio-ffmpeg installed)
- A working virtual environment (recommended)
- Optional: OpenMPT Python binding (pyopenmpt or omp4py) for binary tracker modules

Recommended folders (project root)
- assets/audio_samples/      — short audio samples (wav/mp3/ogg)
- assets/video_samples/      — short video clips used as visual samples
- assets/images/             — fallback images or backgrounds
- examples/plugins/          — example plugins shipped with the project
- output/                    — renders and exported packages

---

Installation

1) Create and activate a virtual environment
- Windows (PowerShell)
  - python -m venv .venv
  - .\.venv\Scripts\Activate.ps1
- macOS / Linux (bash)
  - python -m venv .venv
  - source .venv/bin/activate

2) Install Python dependencies
- pip install -r requirements.txt

Notes:
- If you need moviepy to find ffmpeg, either install ffmpeg system-wide or:
  - pip install imageio-ffmpeg
  - set IMAGEIO_FFMPEG_BINARY env var if needed
- For Windows users: install the Visual C++ Redistributable if any binary wheel complains

3) Install optional OpenMPT bindings (for binary modules)
- pip install pyopenmpt
  or
- pip install omp4py
If one fails, try the other. The project includes an adapter that tries multiple binding names and gives diagnostics.

---

Project layout (key files)
- modpmv/
  - openmpt_adapter.py      — binding adapter for OpenMPT (omp4py/pyopenmpt)
  - mod_parser.py           — parse text modules or binary tracker modules
  - assets.py               — asset resolution helpers
  - audio_renderer.py       — build audio timeline
  - video_renderer.py       — per-channel video composer + ffmpeg concat
  - plugins/
    - base.py               — plugin interfaces
    - loader.py             — plugin discovery
    - marketplace.py        — plugin registry scaffolding
  - gui.py                  — PyQt/PySide GUI (threaded worker)
  - cli.py                  — command-line for headless rendering
  - ytpmv_exporter.py       — package exporter with manifest
  - cache.py, utils.py      — caching & utilities
- examples/plugins/         — example plugins (waveform, beat-slicer, etc.)
- docs/                    — additional docs
- tests/                   — smoke tests

---

First run — GUI quickstart

1) Start the GUI
- python -m modpmv.gui

2) Load a module
- Click "Load module" and open:
  - a text-style .mod file (simple human-readable format shipped in examples)
  - or a binary tracker file (.it / .xm / .mod) if you installed pyopenmpt or omp4py

3) Select asset folders
- Audio assets: e.g., assets/audio_samples
- Video assets: e.g., assets/video_samples
- Images (fallbacks): e.g., assets/images

4) Select optional plugins
- Audio plugin: applies to the produced AudioSegment (e.g., "beat-slicer")
- Visual plugin: can apply a per-row or entire visual transform (e.g., "waveform-visual")
- Enter JSON config in the plugin config editor (raw JSON). Example config:
  {
    "shuffle": true,
    "seed": 42,
    "gain_db": 3
  }

5) Preview
- Click "Preview" (renders a low-res preview, cached) — player opens when ready.

6) Render & Export
- Click "Render & Export" — runs a threaded worker to render audio and video, then exports a YTPMV package to output/.
- Use "Add to Queue" to persist a job to the queue for later processing.

---

Headless run — CLI quickstart

Simple one-line (example):
python -m modpmv.cli --module examples/examples.mod --audio-assets assets/audio_samples --video-assets assets/video_samples --image-assets assets/images --out output

More options:
- --audio-plugin <plugin_name>
- --visual-plugin <plugin_name>
- --mode moviepy|ffmpeg  (ffmpeg mode writes per-row files then concatenates with ffmpeg)

Example:
python -m modpmv.cli --module examples/examples.mod --audio-plugin beat-slicer --visual-plugin waveform-visual --mode ffmpeg --out output/my_export

---

Rendering modes: moviepy vs ffmpeg

moviepy mode
- Composes clips in memory via moviepy and writes final file with moviepy + ffmpeg.
- Easiest to use; good for short previews and moderate-length projects.
- Simpler plugin interactions (moviepy clips returned by plugins).

ffmpeg mode
- Writes per-row video segments (short mp4s) and concatenates them with ffmpeg for the final render.
- Faster and more memory-efficient for long timelines and HD output.
- Requires ffmpeg available in the environment.
- Potential pitfalls: input clip formats and codecs should be compatible for concat; the code attempts re-encode fallback if needed.

Choosing mode
- Use moviepy for prototypes and small projects.
- Use ffmpeg mode for long renders, batch jobs, and production export.

---

OpenMPT bindings (binary module parsing)

Supported bindings: pyopenmpt, omp4py, and other libopenmpt wrappers. The adapter tries multiple constructor patterns; if it fails, it provides diagnostics listing attempted constructors and binding attributes.

Install:
- pip install pyopenmpt
or
- pip install omp4py

If parsing fails with a diagnostic error:
- Run the small introspection snippet suggested in the adapter error to list available attributes and module API.
- Paste output here (or in an issue) and the adapter can be adjusted to call the correct constructors / methods.

Fallback:
- If you cannot install an OpenMPT binding, use the text-format `.mod` (human-readable) files. The text parser maps tokens like SAMPLE:kick into assets.

---

Plugin system

Plugin types
- AudioPlugin / AudioEffectPlugin — take and return pydub.AudioSegment
- VisualPlugin — render(audio_path, duration, size) → moviepy VideoClip
- VisualEffectPlugin — apply(clip) → transformed clip (chainable)
- LayeredVisualPlugin — create_layers(...) → list of layer dicts (clip, z, opacity, blend)

Metadata and discovery
- Class attributes: name, description, tags, version, license, deps
- Discovery: setuptools entry points or local `plugins/` folder (plugins/audio, plugins/visual). The GUI also looks in examples/plugins.

Example plugin config (JSON)
- { "shuffle": true, "seed": 123 }
- Passed to plugin constructor as config argument.

Example plugin locations
- examples/plugins/waveform_visual.py
- examples/plugins/beat_slicer_audio.py

Plugin authoring tips
- Keep preview() method lightweight for GUI responsiveness
- Avoid heavy imports at module import time; use lazy imports inside methods
- Provide sensible defaults and document heavy deps (OpenCV, numba, GPU frameworks)
- Use tags so GUI can filter plugins (e.g., ["waveform","audio-reactive"])

---

Preview, caching & deterministic runs

Preview caching
- Previews are cached in `.modpmv_cache/` keyed by a stable hash of job parameters to avoid re-rendering identical previews.
- To clear cache: remove `.modpmv_cache/` or call cache.clear() if using the API.

Deterministic runs
- For repeatable random behavior, include a `seed` in plugin config and use it (e.g., random.seed(config["seed"])).
- The GUI and CLI show plugin config; include `seed` where randomness is used.

---

Render queue & background worker

- GUI includes a simple job queue (JSON files under `.modpmv_jobs/`) — add jobs with "Add to Queue".
- The RenderWorker runs in a QThread and exposes progress/status signals, canceling support, and emits finished/errored signals.
- For batch production, consider running CLI jobs from a process manager or write a small worker that consumes `.modpmv_jobs/`.

Job manifest example
{
  "module": "examples/examples.mod",
  "audio_assets": "assets/audio_samples",
  "video_assets": "assets/video_samples",
  "image_assets": "assets/images",
  "audio_plugin": "beat-slicer",
  "visual_plugin": "waveform-visual",
  "plugin_config": {"shuffle":true, "seed":42},
  "out": "output",
  "mode": "ffmpeg"
}

---

Packaging YTPMV output

The exporter copies:
- produced audio file (e.g., mytrack_track.mp3)
- produced video (mytrack_video.mp4)
- used video clips into an inner `video_clips/` folder (best-effort copy from detected used files)
- writes `manifest.json` describing module title, order, patterns count, and copied clips

Manifest sample
{
  "module_title": "My Track",
  "audio": "My Track_track.mp3",
  "video": "My Track_video.mp4",
  "copied_video_clips": ["video_clips/kick_clip.mp4", "..."],
  "order": [0],
  "patterns_count": 1
}

---

Troubleshooting & common fixes

1) Qt DLL load failed (ImportError: DLL load failed while importing QtWidgets)
- Ensure a Qt binding is installed (PyQt6, PySide6, PyQt5, or PySide2)
- Ensure MSVC redistributable is installed on Windows
- Confirm Python bitness matches wheel architecture (64-bit Python ↔ 64-bit wheels)

2) moviepy import errors
- pip install moviepy==1.0.3 imageio-ffmpeg
- Ensure ffmpeg is on PATH

3) OpenMPT binding errors
- pip install pyopenmpt or omp4py
- If adapter raises a runtime error listing attempted constructors, paste diagnostics for adapter adjustment

4) ffmpeg concat problems (codec mismatches)
- Ensure per-row files are generated with same codec/format or let the code re-encode (it will attempt to re-encode with libx264)
- For best concat reliability, pre-encode sample clips to mp4/h264 or write a single encode pass

5) Slow renders or memory spikes
- Use ffmpeg mode for long timelines; it generates per-row files and uses concat to avoid holding frames in memory
- Lower preview resolution and fps for GUI previews
- Parallelize batch jobs across multiple worker processes

---

Tips for performance & production

- Convert all audio assets to uncompressed WAV for fastest input reads (or pre-cache decoded WAVs)
- Use consistent video codecs (H.264 MP4) and resolutions for samples to simplify concat pipelines
- Use per-job deterministic seeds to reproduce results
- Pre-generate thumbnails and short loops for preview rather than full renders
- Consider using a render farm / worker pool or Docker containers to isolate environment and guarantee dependency versions

---

Next steps & suggestions

If you want me to:
- Implement a streaming ffmpeg encode pipeline (frame generator → ffmpeg stdin) with multiprocessing frame workers
- Build a form-based plugin config editor that auto-generates UI for plugin metadata
- Improve OpenMPT adapter to support a specific binding API you have installed (share `import omp4py; print(dir(omp4py))` output)
- Add advanced plugins (text-glitch, beat-synced image montage, GPU accelerated displacement)

Tell me which one to implement next and provide:
- a sample binary tracker module (.it/.xm/.mod) if you want precise pattern parsing tests
- info about which OpenMPT binding you have installed (package name/version), or paste the adapter diagnostic if it failed

---

Appendix — Handy commands

Verify Python & pip in venv
python -c "import sys; print(sys.executable)"
python -m pip -V

Install deps
pip install -r requirements.txt

Install ffmpeg on Ubuntu
sudo apt-get update && sudo apt-get install -y ffmpeg

Quick headless render
python -m modpmv.cli --module examples/examples.mod --audio-assets assets/audio_samples --video-assets assets/video_samples --image-assets assets/images --out output

Run tests
pytest -q

---

End of tutorial

If you want I can produce:
- A printable quickstart checklist
- A step-by-step PowerShell script for Windows that automates venv creation, dependency install, ffmpeg PATH setup, and runs a sample preview
- An example binary .it/.xm/.mod sample converted for testing (if you provide or allow sharing)

Which follow-up would you like?