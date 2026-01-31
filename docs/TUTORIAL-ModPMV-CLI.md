# ModPMV CLI — Complete Tutorial

This document explains how to use the ModPMV command-line interface (CLI) to generate YTPMV-style videos from tracker modules and asset libraries. It covers installation, all CLI options, common workflows, job manifests for batch runs, plugin usage, troubleshooting, and CI automation tips.

---

## Quick prerequisites

- Python 3.9+ (64-bit recommended)
- Virtual environment strongly recommended
- FFmpeg installed and on PATH (required for `ffmpeg` and `stream` modes). Alternatively install `imageio-ffmpeg` for a bundled ffmpeg.
- (Optional) A module-tracker binding (package importable as `module_tracker` or whatever your adapter is configured to use) to parse binary `.it` / `.xm` / `.mod` files. If missing, ModPMV falls back to the text `.mod` parser.

---

## Install

1. Create and activate a venv:
   - Windows (PowerShell)
     - python -m venv .venv
     - .\.venv\Scripts\Activate.ps1
   - macOS / Linux
     - python -m venv .venv
     - source .venv/bin/activate

2. Install dependencies:
   - pip install -r requirements.txt

3. Install ffmpeg (if not present):
   - macOS: brew install ffmpeg
   - Ubuntu: sudo apt install ffmpeg
   - Windows: download a build, add its bin to PATH
   - Or: pip install imageio-ffmpeg

4. (Optional) Install module-tracker binding if you need binary tracker parsing:
   - pip install module-tracker
   - If you use a different binding name, update the adapter import names in `modpmv/openmpt_adapter.py`.

---

## CLI entrypoint

Run the CLI with:

```bash
python -m modpmv.cli --module <module_path> [options...]
```

This script runs the entire pipeline (parse module → render audio → render video → package YTPMV export).

---

## CLI options (current scaffold)

- `--module` (required)
  - Path to the module file. Supported: text `.mod` (human-readable) and binary tracker files `.it`, `.xm`, `.mod` (if a binding is available).

- `--audio-assets`
  - Folder containing audio samples. Default: `assets/audio_samples`.

- `--video-assets`
  - Folder containing video sample clips. Default: `assets/video_samples`.

- `--image-assets`
  - Folder for fallback images. Default: `assets/images`.

- `--out`
  - Output folder for rendered assets. Default: `output`.

- `--audio-plugin`
  - Name of an audio plugin (from `plugins/` or entry points). Optional.

- `--visual-plugin`
  - Name of a visual plugin. Optional.

- `--mode`
  - Rendering mode: `moviepy`, `ffmpeg`, or `stream`. Default: `moviepy`.
    - `moviepy`: Compose everything with MoviePy (easy, good for previews).
    - `ffmpeg`: Write per-row mp4s and concat them with ffmpeg (better for long timelines).
    - `stream`: Stream RGB frames into ffmpeg stdin for encoding (low memory, recommended for long HD renders). Requires ffmpeg.

---

## Basic examples

1) Minimal run (moviepy):
```bash
python -m modpmv.cli --module examples/examples.mod --out output/simple
```

2) Use ffmpeg concat mode:
```bash
python -m modpmv.cli \
  --module examples/examples.mod \
  --audio-assets assets/audio_samples \
  --video-assets assets/video_samples \
  --image-assets assets/images \
  --mode ffmpeg \
  --out output/ffmpeg_run
```

3) Stream mode (recommended for long renders):
```bash
python -m modpmv.cli \
  --module examples/examples.mod \
  --mode stream \
  --out output/stream_run
```

4) With plugins (example plugins shipped in `examples/plugins`):
```bash
python -m modpmv.cli --module examples/examples.mod --audio-plugin beat-slicer --visual-plugin waveform-visual --out output/plugins_run
```

Note: Plugin configuration (JSON) is supported by the GUI and job manifest flow. The base CLI scaffold accepts plugin names; if you need to pass plugin config via CLI, see "Passing plugin config" below.

---

## Job / batch workflow

For batch automation create a job manifest (JSON) per job and run a small runner that invokes the CLI for each job or extend the queue consumer.

Example `job1.json`:
```json
{
  "module": "examples/examples.mod",
  "audio_assets": "assets/audio_samples",
  "video_assets": "assets/video_samples",
  "image_assets": "assets/images",
  "audio_plugin": "beat-slicer",
  "visual_plugin": "waveform-visual",
  "plugin_config": {"shuffle": true, "seed": 42},
  "mode": "stream",
  "out": "output/job1"
}
```

Simple runner (Python):
```python
import json, subprocess
job = json.load(open("job1.json"))
cmd = ["python", "-m", "modpmv.cli", "--module", job["module"], "--out", job["out"], "--mode", job.get("mode","moviepy")]
if job.get("audio_plugin"): cmd += ["--audio-plugin", job["audio_plugin"]]
if job.get("visual_plugin"): cmd += ["--visual-plugin", job["visual_plugin"]]
subprocess.check_call(cmd)
```

For production, use a queue consumer that reads `.modpmv_jobs/` (the GUI writes jobs there) and runs the pipeline. You can add retries, concurrency, and logging in such a consumer.

---

## Passing plugin configuration

- The GUI supports raw JSON plugin config (applies to selected plugins).
- The CLI scaffold currently accepts plugin names. To pass plugin config from CLI you can:
  - Extend the CLI to accept `--plugin-config <json-file>` and load it (I can add this if you want), or
  - Put the config inside a job manifest and run via the runner above; the runner can be extended to pass config to the CLI if CLI supports it.

If you want, I can implement `--plugin-config path/to/config.json` that the CLI will read and pass to plugin constructors.

---

## Output & YTPMV package

By default CLI writes:
- `{title}_track.mp3` (audio)
- `{title}_video.mp4` (video)

It also creates a YTPMV package folder under the output path (e.g., `output/<title>_ytpmv_pkg/`) with:
- copied audio & video
- `video_clips/` — copies of used video samples (best-effort)
- `manifest.json` — contains:
  - module_title, audio, video
  - copied_video_clips
  - order, patterns_count
  - `timeline`: list of entries `{start, duration, pattern_index, row_index, used_files}` mapping the rendered video timeline (V5).

You can use the manifest to map sample usage to timestamps for YTPMV post-processing.

---

## Diagnostics & common errors

1) Cannot parse binary module (.it/.xm/.mod)
   - If you use binary tracker files, the adapter needs a binding (module-tracker). If adapter fails the parser writes diagnostics to `output/adapter_diag_*.txt` and falls back to text parsing.
   - Run:
     ```python
     from modpmv.openmpt_adapter import run_diagnostics
     data = open("path/to/module.it","rb").read()
     print(run_diagnostics(data))
     ```
     Paste that output if you want help adapting the adapter.

2) FFmpeg not found
   - If `--mode ffmpeg` or `--mode stream` fails with ffmpeg error, verify `ffmpeg -version` works on your system PATH, or `pip install imageio-ffmpeg`.

3) MoviePy write errors
   - Check ffmpeg availability, file paths, and disk space. For large output, prefer `stream` or `ffmpeg` mode to reduce memory usage.

4) Missing plugins
   - Plugin names must match names discovered by `modpmv.plugins.loader` (local `plugins/` or `examples/plugins`). Check the manifest in GUI or inspect `examples/plugins/`.

5) FileNotFoundError (audio/video sample)
   - The renderer maps `SAMPLE:name` tokens to asset files by base name matching. Verify your asset folder contains corresponding files or that text .mod declarations include `path=` entries.

---

## CI / Automation tips

- On CI runners (GitHub Actions) ensure ffmpeg is installed:
  - Ubuntu example: `sudo apt-get update && sudo apt-get install -y ffmpeg`
- Install Python deps and optionally `imageio-ffmpeg`.
- For smoke tests, run a short `stream` or `moviepy` render of a minimal module and assert outputs exist.
- Use deterministic plugin configs (`seed`) in CI to produce reproducible output.

Example GitHub Actions steps:
```yaml
- uses: actions/checkout@v4
- name: Setup Python
  uses: actions/setup-python@v4
  with: python-version: '3.10'
- name: Install ffmpeg
  run: sudo apt-get install -y ffmpeg
- name: Install deps
  run: pip install -r requirements.txt
- name: Smoke render
  run: python -m modpmv.cli --module examples/examples.mod --mode stream --out ci_output
```

---

## Advanced: stream mode & parallel frame generation

- `stream` mode pipes RGB frames to ffmpeg stdin and lets ffmpeg encode. For best throughput:
  - Produce frames in parallel (worker pool) and write them into a synchronized producer that feeds ffmpeg stdin.
  - Avoid Python-level frame copies where possible. Use numpy arrays of dtype uint8 and write bytes directly.
  - Consider using a separate process for the ffmpeg encoder and use multiprocessing Queues or pipes between worker processes and the encoder.

If you’d like, I can add a `--stream-workers N` option and a built-in worker-pool implementation to the CLI.

---

## Example end-to-end commands

Basic:
```bash
python -m modpmv.cli --module examples/examples.mod --out output/run1
```

ffmpeg concat:
```bash
python -m modpmv.cli --module examples/examples.mod --mode ffmpeg --out output/run2
```

stream:
```bash
python -m modpmv.cli --module examples/examples.mod --mode stream --out output/run3
```

With plugins:
```bash
python -m modpmv.cli --module examples/examples.mod --audio-plugin beat-slicer --visual-plugin waveform-visual --mode stream --out output/plugin_run
```

---

## Next improvements I can add

Tell me which you want and I will produce the code changes:
- `--plugin-config <json-file>` CLI flag to pass plugin configuration.
- A job-consumer CLI to process `.modpmv_jobs/` queue files with retries and concurrency.
- Built-in `--stream-workers` implementation to parallelize frame production for `stream` mode.
- More verbose CLI logging (timings, per-stage durations, profile info).
- Example job runner script and a sample CI workflow that runs a short stream render.

Which enhancement should I implement for you next?