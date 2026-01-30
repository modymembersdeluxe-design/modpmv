# ModPMV

ModPMV — work-in-progress Python GUI & utilities for automatic generation of YTPMV tracks (audio + visuals).

Features (starter)
- .mod parser (simple tracker module reader)
- Audio renderer: automatic clips, sampling, assembly, randomization
- Video renderer: automatic visuals (waveforms, image mashups), synchronized to audio
- GUI (PyQt6 starter) + CLI example

Requirements: see `requirements.txt`.

Next steps
- Provide .mod samples to improve parser
- Choose preferred GUI framework (PyQt6/PySide/Tk/Tkinter)
- Add plugins for custom visual styles and audio sources