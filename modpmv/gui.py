"""
PyQt6 GUI (V2) — assets selection + plugin selection + preview + export pipeline.

This is a starter UI: expand with plugin config editor, progress bars and background worker.
"""
import sys, os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
                             QLabel, QLineEdit, QHBoxLayout, QMessageBox, QComboBox, QTextEdit)
from PyQt6.QtCore import Qt
from modpmv.mod_parser import parse_mod_text
from modpmv.audio_renderer import render_audio_from_module, apply_audio_plugins, export_audio_segment
from modpmv.video_renderer import render_video_from_module
from modpmv.plugins.loader import list_plugins_manifest, discover_plugins
from modpmv.ytpmv_exporter import export_ytpmv_package

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ModPMV V2")
        self.setMinimumSize(720, 320)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # mod loader
        self.mod_path_field = QLineEdit()
        row = QHBoxLayout()
        self.load_mod_btn = QPushButton("Load .mod (text)")
        self.load_mod_btn.clicked.connect(self.choose_mod_file)
        row.addWidget(self.load_mod_btn)
        row.addWidget(self.mod_path_field)
        self.layout.addLayout(row)

        # assets
        self.audio_assets_field = QLineEdit("assets/audio_samples")
        self.video_assets_field = QLineEdit("assets/video_samples")
        self.image_assets_field = QLineEdit("assets/images")
        self.layout.addWidget(QLabel("Audio assets folder:"))
        self.layout.addWidget(self.audio_assets_field)
        self.layout.addWidget(QLabel("Video assets folder (clips):"))
        self.layout.addWidget(self.video_assets_field)
        self.layout.addWidget(QLabel("Images folder (fallbacks):"))
        self.layout.addWidget(self.image_assets_field)

        # plugins manifest + selection
        self.plugin_manifest = list_plugins_manifest("examples/plugins")
        self.audio_plugin_combo = QComboBox()
        self.visual_plugin_combo = QComboBox()
        self._populate_plugin_dropdowns()
        pbox = QHBoxLayout()
        pbox.addWidget(QLabel("Audio plugin:"))
        pbox.addWidget(self.audio_plugin_combo)
        pbox.addWidget(QLabel("Visual plugin:"))
        pbox.addWidget(self.visual_plugin_combo)
        self.layout.addLayout(pbox)

        # plugin config editor (raw JSON) — simple approach for now
        self.config_editor = QTextEdit()
        self.config_editor.setPlaceholderText('Plugin config JSON (applies to both selected plugins)')
        self.layout.addWidget(QLabel("Plugin config (JSON):"))
        self.layout.addWidget(self.config_editor)

        # actions
        self.generate_btn = QPushButton("Render audio + video and export YTPMV package")
        self.generate_btn.clicked.connect(self.generate)
        self.layout.addWidget(self.generate_btn)

        self.status = QLabel("Ready")
        self.status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.addWidget(self.status)

        self.module = None

    def _populate_plugin_dropdowns(self):
        self.audio_plugin_combo.clear()
        self.visual_plugin_combo.clear()
        audio_items = [m for m in self.plugin_manifest if m["type"] == "audio"]
        visual_items = [m for m in self.plugin_manifest if m["type"] == "visual"]
        self.audio_plugin_combo.addItem("none", None)
        self.visual_plugin_combo.addItem("none", None)
        for m in audio_items:
            self.audio_plugin_combo.addItem(m["name"], m)
        for m in visual_items:
            self.visual_plugin_combo.addItem(m["name"], m)

    def choose_mod_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open .mod text", "", "Text Files (*.txt *.mod)")
        if path:
            try:
                self.module = parse_mod_text(path)
                self.mod_path_field.setText(path)
                self.status.setText(f"Loaded module: {self.module.title}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to parse .mod: {e}")

    def generate(self):
        if not self.module:
            QMessageBox.warning(self, "No module", "Please load a .mod text file first.")
            return
        audio_folder = self.audio_assets_field.text().strip() or "assets/audio_samples"
        video_folder = self.video_assets_field.text().strip() or "assets/video_samples"
        image_folder = self.image_assets_field.text().strip() or "assets/images"
        try:
            self.status.setText("Rendering audio...")
            audio_seg = render_audio_from_module(self.module, [audio_folder])
            # load audio plugin if selected
            audio_plugin_meta = self.audio_plugin_combo.currentData()
            audio_plugins = []
            if audio_plugin_meta:
                cls = audio_plugin_meta["class"]
                import json
                cfg = {}
                try:
                    cfg = json.loads(self.config_editor.toPlainText() or "{}")
                except Exception:
                    cfg = {}
                audio_plugins.append(cls(config=cfg))
            audio_seg = apply_audio_plugins(audio_seg, audio_plugins)
            out_audio = os.path.join("output", f"{self.module.title}_track.mp3")
            export_audio_segment(audio_seg, out_audio)
            self.status.setText("Rendering video...")
            visual_plugin_meta = self.visual_plugin_combo.currentData()
            visual_plugins = []
            if visual_plugin_meta:
                cls = visual_plugin_meta["class"]
                import json
                cfg = {}
                try:
                    cfg = json.loads(self.config_editor.toPlainText() or "{}")
                except Exception:
                    cfg = {}
                visual_plugins.append(cls(config=cfg))
            out_video = os.path.join("output", f"{self.module.title}_video.mp4")
            render_video_from_module(self.module, out_audio, [video_folder], [image_folder], out_video, visual_plugins=visual_plugins)
            # simple used video collection: copy entire video folder for now
            used_videos = []
            if os.path.isdir(video_folder):
                for fn in os.listdir(video_folder):
                    if fn.lower().endswith((".mp4",".mov",".webm",".avi")):
                        used_videos.append(os.path.join(video_folder, fn))
            out_pkg = os.path.join("output", f"{self.module.title}_ytpmv_pkg")
            manifest = export_ytpmv_package(self.module, out_audio, out_video, used_videos, out_pkg)
            self.status.setText(f"Done — package: {out_pkg}")
            QMessageBox.information(self, "Done", f"Exported YTPMV package at:\n{out_pkg}\nManifest: {manifest}")
        except Exception as e:
            QMessageBox.critical(self, "Render error", f"An error occurred: {e}")
            self.status.setText("Error during generation")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())