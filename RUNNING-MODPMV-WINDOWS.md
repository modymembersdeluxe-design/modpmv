# Running ModPMV (Windows 7 / 8.1 / 10 / 11) — Practical Guide

This guide shows how to set up and run ModPMV (V2) on Windows. It covers system prerequisites, installing Python and dependencies, FFmpeg, virtual environments, running the GUI and CLI, troubleshooting, and compatibility notes for older Windows (7 / 8.1).

Quick note about Windows versions
- Windows 10 and 11: recommended. Most dependencies (Python 3.9+, PyQt6, moviepy, pydub) work well here.
- Windows 8.1: should work for most cases; prefer Python 3.9+.
- Windows 7: legacy. Newer Python releases and some wheels may not support Win7. If you must use Windows 7, prefer Python 3.8 and PyQt5/PySide2 and be ready to use alternate wheels or build steps for some packages. See the "Windows 7 specific notes" section later.

Contents
- 1) Tools & downloads
- 2) Install Python and prepare a virtual environment
- 3) Install FFmpeg and add to PATH
- 4) Install ModPMV dependencies
- 5) Run GUI and CLI examples
- 6) Optional: using PySide / PyQt5 for older Windows
- 7) Windows 7 compatibility tips
- 8) Common errors & troubleshooting
- 9) Helpful commands & environment variables

---

1) Tools & downloads
- Python: download from [python.org](https://www.python.org/downloads/windows/). Choose 64-bit if your Windows is 64-bit.
- FFmpeg: download a Windows build (static) — e.g.:
  - BtbN builds: https://github.com/BtbN/FFmpeg-Builds/releases
  - Gyan builds: https://www.gyan.dev/ffmpeg/builds/
  Pick a "release" static build and extract the `bin\ffmpeg.exe`.
- (Optional) Microsoft Visual C++ Redistributable: sometimes required for binary wheels. Download from Microsoft: https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist

---

2) Install Python and prepare a virtual environment (PowerShell or CMD)
Open PowerShell (recommended) or CMD as a normal user.

- Verify Python is installed:
```powershell
python --version
```

- Create and activate a virtual environment (PowerShell):
```powershell
cd C:\path\to\modpmv-repo
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
# If using CMD:
# .\.venv\Scripts\activate.bat
```

If PowerShell blocks script execution on activation, run (Admin) once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

3) Install FFmpeg and add to PATH
1. Extract a static FFmpeg build to e.g. `C:\ffmpeg\` so `C:\ffmpeg\bin\ffmpeg.exe` exists.
2. Add `C:\ffmpeg\bin` to your system PATH:
   - System (GUI): Control Panel → System → Advanced system settings → Environment Variables → edit `Path` → Add `C:\ffmpeg\bin`
   - Or via PowerShell (for current user):
     ```powershell
     setx PATH "$($env:Path);C:\ffmpeg\bin"
     ```
     After setx you must open a new shell to see the change.

3. Verify:
```powershell
ffmpeg -version
```

Optional: point moviepy/pydub at ffmpeg explicitly in your session:
```powershell
$env:FFMPEG_BINARY = "C:\ffmpeg\bin\ffmpeg.exe"
# For pydub:
$env:PATH = "C:\ffmpeg\bin;$env:PATH"
```

---

4) Install ModPMV dependencies
Inside your activated virtualenv:

- If the repo has requirements.txt:
```powershell
pip install -U pip setuptools wheel
pip install -r requirements.txt
```

- If you prefer to install manually:
```powershell
pip install PyQt6 pydub moviepy librosa numpy soundfile
```

Notes:
- `soundfile` (pysoundfile) may require a libsndfile DLL on some systems; usually pip wheels include what you need, but if you see errors, install a prebuilt wheel or use conda.
- If any package fails to install due to missing compilers, try installing the Visual C++ redistributable or use compatible wheels.

---

5) Run ModPMV — GUI and CLI examples
- GUI
```powershell
python -m modpmv.gui
```
The GUI allows: loading a `.mod` text file, selecting asset folders (audio/video/images), choosing plugins (from `examples/plugins` or `plugins/`), entering JSON config for plugins, then Render & Export.

- Headless CLI (example)
If your project provides a CLI module (or use the example script), run:
```powershell
python -m modpmv.cli --audio-assets "assets\audio_samples" --img-assets "assets\images" --out "output\demo_track.mp3"
```
Or run an example script:
```powershell
python examples\generate_example.py
```

- Output files will appear in `output\` by default (audio `.mp3` and video `.mp4`, plus an exported YTPMV package folder).

---

6) Optional: Using PySide or PyQt5 on older Windows
- If PyQt6 fails to install or run (older OS or old Qt dependency), try:
  - PySide6 (API close to PyQt6): `pip install PySide6`
  - PyQt5 (supports older Windows): `pip install PyQt5`
- Modify `modpmv/gui.py` imports if you switch to PySide6 (class names are similar) or keep `PyQt6` and install the chosen package that provides compatible API.

Example: switch to PySide6 quickly (one-off):
```powershell
pip uninstall PyQt6
pip install PySide6
# In code, change imports:
# from PyQt6.QtWidgets import ...  -> from PySide6.QtWidgets import ...
```
(You can also implement a small adapter wrapper for compatibility.)

---

7) Windows 7 compatibility notes
- Python: newer Python versions (3.9+) may not fully support Windows 7. If you must use Windows 7:
  - Prefer Python 3.8.x (last to officially support Win7 in many cases).
  - Use PyQt5 or PySide2 instead of PyQt6/PySide6.
  - Some binary wheels may not be available; you may need to build from source or use conda.
- Consider upgrading OS to Windows 10/11 for best experience and dependency support.

---

8) Common errors & troubleshooting

- "ffmpeg not found" or "MoviePy error: FFmpeg is required"
  - Ensure `ffmpeg.exe` is on PATH or set `FFMPEG_BINARY` environment var pointing to ffmpeg.exe.
  - Restart terminal after changing PATH.

- "ImportError: PyQt6" or GUI fails to start
  - Confirm PyQt6 installed in the active virtualenv: `pip show PyQt6`
  - If installing PyQt6 fails, try PySide6 or PyQt5.
  - For Windows 7/8: use PyQt5/PySide2.

- "soundfile" or "libsndfile" load errors
  - Install the Visual C++ redistributable.
  - Use conda (recommended on Windows) to install soundfile/libsndfile without compiling:
    - `conda install -c conda-forge pysoundfile libsndfile`

- "Permission denied" when writing to `output/`
  - Run in a directory where you have write permissions (avoid Program Files).
  - Ensure antivirus isn't blocking ffmpeg or your script.

- Long path or Unicode path issues
  - Use short paths without special characters; enable long path support in Windows 10+ if needed.
  - Run Python from a path without non-ASCII characters to avoid encoding footguns with some libraries.

- MoviePy slow render or crashes on large renders
  - For previews, reduce resolution and fps.
  - Try rendering in segments and use ffmpeg to concatenate.
  - Increase swap or use smaller batch sizes.

---

9) Helpful commands & environment variables

- Activate venv (PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```

- Set ffmpeg for current session:
```powershell
$env:FFMPEG_BINARY = "C:\ffmpeg\bin\ffmpeg.exe"
$env:PATH = "C:\ffmpeg\bin;$env:PATH"
```

- Verify ffmpeg:
```powershell
ffmpeg -version
```

- Verify Python and pip packages:
```powershell
python -c "import sys; print(sys.version)"
python -c "import moviepy, pydub; print(moviepy.__version__, pydub.__version__)"
```

- Example headless job (PowerShell):
```powershell
python - <<'PY'
from modpmv.mod_parser import parse_mod_text
from modpmv.audio_renderer import render_audio_from_module, export_audio_segment
from modpmv.video_renderer import render_video_from_module
m = parse_mod_text("examples\\demo.mod")
audio = render_audio_from_module(m, ["assets\\audio_samples"])
export_audio_segment(audio, "output\\demo.mp3")
render_video_from_module(m, "output\\demo.mp3", ["assets\\video_samples"], ["assets\\images"], "output\\demo.mp4")
print("Done")
PY
```

---

Final tips
- Start with small test assets (short audio clips and small images) and low resolution (640x360, 24fps) while fine-tuning.
- Use deterministic seeds for any random choices in plugins to reproduce results.
- If you plan production or many renders, prefer a modern Windows (10/11) environment with updated Python and ffmpeg.

If you want, I can:
- Create a Windows-specific step-by-step script (PowerShell) that automates venv creation, installs dependencies and configures ffmpeg PATH.
- Add a short video walkthrough showing GUI steps on Windows.
- Provide a PyQt5-compatible GUI file and adjusted requirements for Windows 7/8.1 users.

Which of those would you like next?