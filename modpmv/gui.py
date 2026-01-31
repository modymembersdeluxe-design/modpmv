"""
PyQt GUI (Deluxe) with a threaded render worker, plugin manifest UI, preview, queueing, and progress updates.

This is a starter but production-capable UI:
- uses QThread for background render work
- shows status and allows adding jobs to the queue
- plugin config is raw JSON for now (can be upgraded to form-based)
"""
# Qt binding fallback
_try = None
for lib in ("PyQt6","PySide6","PyQt5","PySide2"):
    try:
        if lib=="PyQt6":
            from PyQt6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QPushButton,QFileDialog,QLabel,QLineEdit,QHBoxLayout,QMessageBox,QComboBox,QTextEdit,QProgressBar)
            from PyQt6.QtCore import Qt, QThread, pyqtSignal
        elif lib=="PySide6":
            from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QPushButton,QFileDialog,QLabel,QLineEdit,QHBoxLayout,QMessageBox,QComboBox,QTextEdit,QProgressBar)
            from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal
        elif lib=="PyQt5":
            from PyQt5.QtWidgets import (QApplication,QWidget,QVBoxLayout,QPushButton,QFileDialog,QLabel,QLineEdit,QHBoxLayout,QMessageBox,QComboBox,QTextEdit,QProgressBar)
            from PyQt5.QtCore import Qt, QThread, pyqtSignal
        else:
            from PySide2.QtWidgets import (QApplication,QWidget,QVBoxLayout,QPushButton,QFileDialog,QLabel,QLineEdit,QHBoxLayout,QMessageBox,QComboBox,QTextEdit,QProgressBar)
            from PySide2.QtCore import Qt, QThread, Signal as pyqtSignal
        _try = lib; break
    except Exception:
        _try = None; continue
if _try is None:
    raise ImportError("No supported Qt binding found. Install PyQt6 or PySide6 (or PyQt5/PySide2).")

import json, os, time
from modpmv.mod_parser import parse
from modpmv.audio_renderer import render_audio_from_module_data, apply_audio_plugins, export_audio_segment
from modpmv.video_renderer import render_preview, render_video_from_module_data
from modpmv.plugins.loader import list_plugins_manifest, discover_plugins
from modpmv.ytpmv_exporter import export_ytpmv_package
from modpmv.queue import push_job, list_jobs, load_job, pop_job
from modpmv.utils import ensure_dir

class RenderWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    errored = pyqtSignal(str)

    def __init__(self, job: dict, parent=None):
        super().__init__(parent)
        self.job = job
        self._cancel = False

    def run(self):
        try:
            self.status.emit("Parsing module...")
            module_data = parse(self.job["module"])
            self.status.emit("Rendering audio...")
            audio = render_audio_from_module_data(module_data, [self.job.get("audio_assets","assets/audio_samples")])
            # audio plugins handled by name => instantiate if available
            if self.job.get("audio_plugin"):
                avail = discover_plugins().get("audio", {})
                cls = avail.get(self.job["audio_plugin"])
                if cls:
                    audio = apply_audio_plugins(audio, [cls(config=self.job.get("plugin_config", {}))])
            out_dir = self.job.get("out","output")
            ensure_dir(out_dir)
            out_audio = os.path.join(out_dir, f"{module_data.get('title')}_track.mp3")
            export_audio_segment(audio, out_audio)
            self.progress.emit(40)
            if self._cancel:
                self.status.emit("Cancelled")
                self.finished.emit("cancelled")
                return
            self.status.emit("Rendering video...")
            visual_plugins = []
            if self.job.get("visual_plugin"):
                vavail = discover_plugins().get("visual", {})
                vcls = vavail.get(self.job["visual_plugin"])
                if vcls:
                    visual_plugins.append(vcls(config=self.job.get("plugin_config", {})))
            out_video = os.path.join(out_dir, f"{module_data.get('title')}_video.mp4")
            render_video_from_module_data(module_data, out_audio, [self.job.get("video_assets","assets/video_samples")], [self.job.get("image_assets","assets/images")], out_video, visual_plugins=visual_plugins, mode=self.job.get("mode","moviepy"))
            self.progress.emit(90)
            self.status.emit("Exporting package...")
            used = []  # best-effort; renderer may return used files in an improved version
            manifest = export_ytpmv_package(module_data, out_audio, out_video, used, os.path.join(out_dir, f"{module_data.get('title')}_ytpmv_pkg"))
            self.progress.emit(100)
            self.status.emit("Done")
            self.finished.emit(manifest)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.errored.emit(str(tb))

    def cancel(self):
        self._cancel = True

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ModPMV V4 Deluxe - Qt: {_try}")
        self.setMinimumSize(1100,600)
        self.layout = QVBoxLayout(); self.setLayout(self.layout)
        # module load
        self.module_field = QLineEdit()
        row = QHBoxLayout()
        self.load_btn = QPushButton("Load module")
        self.load_btn.clicked.connect(self.choose_module)
        row.addWidget(self.load_btn); row.addWidget(self.module_field)
        self.layout.addLayout(row)
        # asset fields
        self.audio_assets = QLineEdit("assets/audio_samples"); self.video_assets = QLineEdit("assets/video_samples"); self.image_assets = QLineEdit("assets/images")
        self.layout.addWidget(QLabel("Audio assets:")); self.layout.addWidget(self.audio_assets)
        self.layout.addWidget(QLabel("Video assets:")); self.layout.addWidget(self.video_assets)
        self.layout.addWidget(QLabel("Image assets:")); self.layout.addWidget(self.image_assets)
        # plugins
        self.manifest = list_plugins_manifest("examples/plugins")
        self.audio_combo = QComboBox(); self.visual_combo = QComboBox()
        self._populate_plugins()
        ph = QHBoxLayout(); ph.addWidget(QLabel("Audio plugin:")); ph.addWidget(self.audio_combo); ph.addWidget(QLabel("Visual plugin:")); ph.addWidget(self.visual_combo)
        self.layout.addLayout(ph)
        # config editor
        self.cfg_editor = QTextEdit(); self.cfg_editor.setPlaceholderText("Plugin config JSON for selected plugins")
        self.layout.addWidget(QLabel("Plugin config (JSON):")); self.layout.addWidget(self.cfg_editor)
        # actions
        actions = QHBoxLayout()
        self.preview_btn = QPushButton("Preview"); self.preview_btn.clicked.connect(self.preview)
        self.render_btn = QPushButton("Render & Export"); self.render_btn.clicked.connect(self.render_and_export)
        actions.addWidget(self.preview_btn); actions.addWidget(self.render_btn)
        self.layout.addLayout(actions)
        # progress & queue
        qbox = QHBoxLayout()
        self.progress = QProgressBar(); self.progress.setValue(0)
        qbox.addWidget(self.progress)
        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.clicked.connect(self.cancel_job)
        qbox.addWidget(self.cancel_btn)
        self.layout.addLayout(qbox)
        # queue controls
        qh = QHBoxLayout()
        self.queue_add = QPushButton("Add to Queue"); self.queue_add.clicked.connect(self.add_to_queue)
        self.queue_list = QComboBox(); self.queue_refresh = QPushButton("Refresh Queue"); self.queue_refresh.clicked.connect(self._refresh_queue)
        qh.addWidget(self.queue_add); qh.addWidget(self.queue_list); qh.addWidget(self.queue_refresh)
        self.layout.addLayout(qh)
        self.status = QLabel("Ready"); self.layout.addWidget(self.status)
        self.worker = None
        self._refresh_queue()

    def _populate_plugins(self):
        self.audio_combo.clear(); self.visual_combo.clear()
        self.audio_combo.addItem("none", None); self.visual_combo.addItem("none", None)
        for m in self.manifest:
            if m["type"]=="audio": self.audio_combo.addItem(m["name"], m)
            if m["type"]=="visual": self.visual_combo.addItem(m["name"], m)

    def choose_module(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open module", "", "Tracker modules (*.it *.xm *.mod);;Text module (*.txt *.mod)")
        if not path: return
        try:
            # quick parse to show title
            md = parse(path)
            self.module_field.setText(path)
            self.status.setText(f"Loaded: {md.get('title')}")
        except Exception as e:
            QMessageBox.critical(self, "Parse error", str(e)); self.status.setText("Load failed")

    def _load_selected_plugins(self):
        cfg={}
        try: cfg = json.loads(self.cfg_editor.toPlainText() or "{}")
        except Exception: cfg={}
        a_meta = self.audio_combo.currentData(); v_meta = self.visual_combo.currentData()
        a_name = a_meta["name"] if a_meta else None
        v_name = v_meta["name"] if v_meta else None
        return a_name, v_name, cfg

    def preview(self):
        path = self.module_field.text().strip()
        if not path:
            QMessageBox.warning(self, "No module", "Load a module first"); return
        a_name, v_name, cfg = self._load_selected_plugins()
        a_folders=[self.audio_assets.text()]; v_folders=[self.video_assets.text()]; i_folders=[self.image_assets.text()]
        # instantiate visual plugin if available
        vps=[]
        if v_name:
            vcls = discover_plugins().get("visual", {}).get(v_name)
            if vcls: vps.append(vcls(config=cfg))
        try:
            self.status.setText("Rendering preview...")
            out = render_preview(path, a_folders, v_folders, i_folders, preview_seconds=6.0, out_path="output/preview.mp4", size=(640,360), visual_plugins=vps, mode="moviepy")
            self.status.setText("Preview ready: "+out)
            QMessageBox.information(self, "Preview", "Preview created: "+out)
        except Exception as e:
            QMessageBox.critical(self, "Preview error", str(e)); self.status.setText("Preview failed")

    def render_and_export(self):
        path = self.module_field.text().strip()
        if not path:
            QMessageBox.warning(self,"No module","Load a module first"); return
        a_name, v_name, cfg = self._load_selected_plugins()
        job = {
            "module": path,
            "audio_assets": self.audio_assets.text(),
            "video_assets": self.video_assets.text(),
            "image_assets": self.image_assets.text(),
            "audio_plugin": a_name,
            "visual_plugin": v_name,
            "plugin_config": cfg,
            "out": "output",
            "mode": "moviepy"
        }
        # run worker thread
        self.worker = RenderWorker(job)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(lambda s: self.status.setText(s))
        self.worker.finished.connect(lambda m: QMessageBox.information(self,"Done",f"Exported: {m}"))
        self.worker.errored.connect(lambda e: QMessageBox.critical(self,"Error",e))
        self.worker.start()

    def cancel_job(self):
        if self.worker:
            self.worker.cancel()
            self.status.setText("Cancelling...")

    def add_to_queue(self):
        path = self.module_field.text().strip()
        if not path:
            QMessageBox.warning(self,"No module","Load a module first"); return
        job_id = os.path.splitext(os.path.basename(path))[0] + "_" + str(int(time.time()))
        a_name, v_name, cfg = self._load_selected_plugins()
        job = {"module": path, "audio_assets": self.audio_assets.text(), "video_assets": self.video_assets.text(), "image_assets": self.image_assets.text(), "audio_plugin": a_name, "visual_plugin": v_name, "plugin_config": cfg, "out": "output"}
        push_job(job_id, job)
        self._refresh_queue()
        QMessageBox.information(self,"Queue","Added job: "+job_id)

    def _refresh_queue(self):
        self.queue_list.clear()
        for f in list_jobs():
            self.queue_list.addItem(f)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    w = MainWindow(); w.show()
    sys.exit(app.exec())