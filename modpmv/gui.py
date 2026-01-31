"""
PyQt GUI (V3) — compatibility import fallback, plugin manifest UI, plugin config editor (JSON),
Preview button (uses render_preview), Render queue (simplified), status bar.

This GUI is a starter: for production add background threads for rendering and progress reporting.
"""
# Try Qt bindings in order: PyQt6, PySide6, PyQt5, PySide2
_try_gui = None
for lib in ("PyQt6", "PySide6", "PyQt5", "PySide2"):
    try:
        if lib == "PyQt6":
            from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
                                         QLabel, QLineEdit, QHBoxLayout, QMessageBox, QComboBox, QTextEdit)
            from PyQt6.QtCore import Qt
        elif lib == "PySide6":
            from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
                                           QLabel, QLineEdit, QHBoxLayout, QMessageBox, QComboBox, QTextEdit)
            from PySide6.QtCore import Qt
        elif lib == "PyQt5":
            from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
                                         QLabel, QLineEdit, QHBoxLayout, QMessageBox, QComboBox, QTextEdit)
            from PyQt5.QtCore import Qt
        else:
            from PySide2.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
                                           QLabel, QLineEdit, QHBoxLayout, QMessageBox, QComboBox, QTextEdit)
            from PySide2.QtCore import Qt
        _try_gui = lib
        break
    except Exception:
        _try_gui = None
        continue

if _try_gui is None:
    raise ImportError("No supported Qt binding found. Install PyQt6 or PySide6 (or PyQt5/PySide2 for legacy).")

import json, os
from modpmv.mod_parser import parse
from modpmv.audio_renderer import render_audio_from_module_data, apply_audio_plugins, export_audio_segment
from modpmv.video_renderer import render_preview, render_video_from_module_data
from modpmv.plugins.loader import list_plugins_manifest, discover_plugins
from modpmv.ytpmv_exporter import export_ytpmv_package
from modpmv.utils import ensure_dir

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ModPMV V3 - Qt: {_try_gui}")
        self.setMinimumSize(900, 420)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Module loader
        self.mod_path = QLineEdit()
        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("Load module (.it/.xm/.mod/.mod.txt)")
        self.load_btn.clicked.connect(self.choose_module)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.mod_path)
        self.layout.addLayout(btn_row)

        # Asset selectors
        self.audio_assets = QLineEdit("assets/audio_samples")
        self.video_assets = QLineEdit("assets/video_samples")
        self.images_assets = QLineEdit("assets/images")
        self.layout.addWidget(QLabel("Audio assets folder:"))
        self.layout.addWidget(self.audio_assets)
        self.layout.addWidget(QLabel("Video assets folder:"))
        self.layout.addWidget(self.video_assets)
        self.layout.addWidget(QLabel("Images folder (fallback):"))
        self.layout.addWidget(self.images_assets)

        # Plugins
        self.plugin_manifest = list_plugins_manifest("examples/plugins")
        self.audio_combo = QComboBox()
        self.visual_combo = QComboBox()
        self._populate_plugins()
        ph = QHBoxLayout()
        ph.addWidget(QLabel("Audio plugin:")); ph.addWidget(self.audio_combo)
        ph.addWidget(QLabel("Visual plugin:")); ph.addWidget(self.visual_combo)
        self.layout.addLayout(ph)

        # Plugin config editor (JSON)
        self.config_editor = QTextEdit()
        self.config_editor.setPlaceholderText('Plugin config JSON (applies to selected plugins)')
        self.layout.addWidget(QLabel("Plugin config (JSON):"))
        self.layout.addWidget(self.config_editor)

        # Actions row
        actions = QHBoxLayout()
        self.preview_btn = QPushButton("Preview (low-res)")
        self.preview_btn.clicked.connect(self.preview)
        self.render_btn = QPushButton("Render & Export")
        self.render_btn.clicked.connect(self.render_and_export)
        actions.addWidget(self.preview_btn); actions.addWidget(self.render_btn)
        self.layout.addLayout(actions)

        self.status = QLabel("Ready")
        self.layout.addWidget(self.status)

        self.module_data = None

    def _populate_plugins(self):
        self.audio_combo.clear()
        self.visual_combo.clear()
        self.audio_combo.addItem("none", None)
        self.visual_combo.addItem("none", None)
        for m in self.plugin_manifest:
            if m["type"] == "audio":
                self.audio_combo.addItem(m["name"], m)
            if m["type"] == "visual":
                self.visual_combo.addItem(m["name"], m)

    def choose_module(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open module", "", "Tracker modules (*.it *.xm *.mod);;Text module (*.txt *.mod)")
        if not path:
            return
        try:
            self.module_data = parse(path)
            self.mod_path.setText(path)
            self.status.setText(f"Loaded module: {self.module_data.get('title')}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse module: {e}")
            self.status.setText("Failed to load module")

    def _load_selected_plugins(self):
        import json
        cfg = {}
        try:
            cfg = json.loads(self.config_editor.toPlainText() or "{}")
        except Exception:
            cfg = {}
        audio_meta = self.audio_combo.currentData()
        visual_meta = self.visual_combo.currentData()
        audio_plugins = []
        visual_plugins = []
        if audio_meta:
            cls = audio_meta["class"]
            audio_plugins.append(cls(config=cfg))
        if visual_meta:
            clsv = visual_meta["class"]
            visual_plugins.append(clsv(config=cfg))
        return audio_plugins, visual_plugins

    def preview(self):
        if not self.module_data:
            QMessageBox.warning(self, "No module", "Load a module first")
            return
        audio_folders = [self.audio_assets.text()]
        video_folders = [self.video_assets.text()]
        image_folders = [self.images_assets.text()]
        _, visual_plugins = self._load_selected_plugins()
        try:
            self.status.setText("Rendering preview...")
            out = render_preview(self.mod_path.text(), audio_folders, video_folders, image_folders, preview_seconds=6.0, out_path="output/preview.mp4", visual_plugins=visual_plugins)
            self.status.setText("Preview generated: " + out)
            QMessageBox.information(self, "Preview ready", f"Preview saved to: {out}")
        except Exception as e:
            QMessageBox.critical(self, "Preview error", str(e))
            self.status.setText("Preview failed")

    def render_and_export(self):
        if not self.module_data:
            QMessageBox.warning(self, "No module", "Load a module first")
            return
        audio_folders = [self.audio_assets.text()]
        video_folders = [self.video_assets.text()]
        image_folders = [self.images_assets.text()]
        audio_plugins, visual_plugins = self._load_selected_plugins()
        try:
            self.status.setText("Rendering audio...")
            audio_seg = render_audio_from_module_data(self.module_data, audio_folders)
            # apply audio plugins chain
            audio_seg = apply_audio_plugins(audio_seg, audio_plugins)
            ensure_dir("output")
            out_audio = os.path.join("output", f"{self.module_data.get('title')}_track.mp3")
            export_audio_segment(audio_seg, out_audio)
            self.status.setText("Rendering video...")
            out_video = os.path.join("output", f"{self.module_data.get('title')}_video.mp4")
            render_video_from_module_data(self.module_data, out_audio, video_folders, image_folders, out_video, visual_plugins=visual_plugins)
            # collect used videos (best-effort from video folder)
            used = []
            for f in os.listdir(video_folders[0]) if os.path.isdir(video_folders[0]) else []:
                if f.lower().endswith((".mp4",".mov",".webm",".avi")):
                    used.append(os.path.join(video_folders[0], f))
            pkg = os.path.join("output", f"{self.module_data.get('title')}_ytpmv_pkg")
            manifest = export_ytpmv_package(self.module_data, out_audio, out_video, used, pkg)
            self.status.setText("Export done: " + pkg)
            QMessageBox.information(self, "Export", f"Exported package to:\n{pkg}\nManifest: {manifest}")
        except Exception as e:
            QMessageBox.critical(self, "Render error", str(e))
            self.status.setText("Render failed")

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())