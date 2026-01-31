# ModPMV V5 Deluxe — YTPMV Generation (Overview & Quickstart)

ModPMV V5 Deluxe is the next major iteration of ModPMV focused on reliable YTPMV generation from tracker modules, asset libraries and plugin-driven audio/visual pipelines.

Key V5 highlights
- YTPMV-first exporter with precise timestamped timeline and packaging.
- Streaming FFmpeg encode mode (ffmpeg stdin) for low-memory, high-throughput renders.
- Improved Module-Tracker adapter with diagnostics and safe fallbacks.
- Per-channel mapping UI and presets (GUI), plus render queue and threaded worker.
- Plugin manifest + marketplace scaffolding and preview hooks.
- Robust moviepy and ffmpeg fallback behavior.
- Improved tests and CI workflow scaffolding.

Quick start (summary)
1. Create & activate a venv:
   - python -m venv .venv
   - Windows: .\.venv\Scripts\Activate.ps1 or .\.venv\Scripts\activate.bat
   - macOS/Linux: source .venv/bin/activate
2. Install dependencies:
   - pip install -r requirements.txt
3. Install FFmpeg (system PATH) or pip install imageio-ffmpeg
4. Optional: install your module-tracker binding (package name used by your environment)
5. Prepare asset folders:
   - assets/audio_samples/, assets/video_samples/, assets/images/
6. Run GUI:
   - python -m modpmv.gui
7. Or run headless:
   - python -m modpmv.cli --module examples/examples.mod --out output

What’s in this release
- Files updated/added: pyproject.toml, requirements.txt, many files in modpmv/ (adapter, parser, renderers, exporter, CLI, GUI), tests/
- Streaming encode mode: `mode=stream` uses ffmpeg stdin to receive raw frames for more scalable renders.
- YTPMV exporter consumes the timeline returned by video renderer and writes a manifest with per-row start/duration and used clip mapping.

Caveats & notes
- Streaming encode is more efficient for long HD renders but requires a working ffmpeg binary.
- Module parsing requires a binding (project-specific name e.g. `module-tracker`) or you can use the text-format `.mod` fallback.
- This release favors defensiveness: parse falls back to text parsing and stores diagnostics if a binding is broken.

If you want, I can:
- Wire full automated CI tests executing a short sample render using the `stream` mode (needs ffmpeg on runner).
- Add a form-based plugin config UI (auto-generated from plugin metadata).
- Convert heavy per-frame visual effects to a worker pool to parallelize frame generation before piping to ffmpeg.

Which would you like next?