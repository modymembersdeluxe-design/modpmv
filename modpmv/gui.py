"""
Minimal PyQt6 GUI (starter) to glue parsers/renderers together.
This is intentionally small — extend with settings, progress bars, preview widgets.
"""
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel
from modpmv.mod_parser import parse_mod_text
from modpmv.audio_renderer import random_clip_from_folder, assemble_track, export_track
from modpmv.video_renderer import render_video_for_audio

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ModPMV - Starter")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.label = QLabel("No file loaded")
        self.layout.addWidget(self.label)

        self.load_btn = QPushButton("Load .mod (text demo)")
        self.load_btn.clicked.connect(self.load_mod)
        self.layout.addWidget(self.load_btn)

        self.gen_btn = QPushButton("Generate (audio+video)")
        self.gen_btn.clicked.connect(self.generate)
        self.layout.addWidget(self.gen_btn)

    def load_mod(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open .mod text", "", "Text Files (*.txt *.mod)")
        if path:
            mod = parse_mod_text(path)
            self.label.setText(f"Loaded: {mod.title}")

    def generate(self):
        # demo: build a short audio by sampling random clips from assets/audio
        try:
            clips = [random_clip_from_folder("assets/audio", length_ms=1500) for _ in range(8)]
            track = assemble_track(clips)
            out_audio = "output/demo_track.mp3"
            os.makedirs("output", exist_ok=True)
            export_track(track, out_audio)
            render_video_for_audio(out_audio, "assets/images", "output/demo_video.mp4")
            self.label.setText("Generated output/demo_video.mp4")
        except Exception as e:
            self.label.setText("Error: " + str(e))

if __name__ == "__main__":
    import os
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())