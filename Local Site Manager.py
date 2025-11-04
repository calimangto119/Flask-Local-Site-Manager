import sys, subprocess, importlib

# --- Auto-install required packages ---
required = ["PyQt5", "flask", "waitress"]
for pkg in required:
    try:
        importlib.import_module(pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", pkg], check=True)

# Now safely import after ensuring packages exist
import os, json, shutil, zipfile, socket, webbrowser, time
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QListWidget, QTextEdit, QProgressBar, QMessageBox,
    QTabWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer


BASE_DIR = Path("C:/PersonalSites")
ARCHIVE_DIR = BASE_DIR / "_archive"
META_FILE = BASE_DIR / "sites.json"

# Cache for port checking to avoid repeated socket operations
_port_cache = {}
_cache_timeout = 2.0  # seconds

def load_metadata():
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}

def save_metadata(data):
    # Use atomic write to prevent corruption
    temp_file = META_FILE.with_suffix('.tmp')
    temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_file.replace(META_FILE)

def get_used_ports(meta):
    used = set()
    for s in meta.values():
        if s.get("archived"):
            continue
        port = s.get("port")
        if port:
            used.add(port)
    return used

def get_next_port(meta):
    port = 5000
    used = get_used_ports(meta)
    while port in used:
        port += 1
    return port

def port_in_use(port):
    """Cached port checking with timeout"""
    current_time = time.time()
    cache_key = f"port_{port}"
    
    if cache_key in _port_cache:
        cached_result, timestamp = _port_cache[cache_key]
        if current_time - timestamp < _cache_timeout:
            return cached_result
    
    # Actual port check with timeout
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)  # 1 second timeout
            result = s.connect_ex(("127.0.0.1", port)) == 0
            _port_cache[cache_key] = (result, current_time)
            return result
    except:
        return False

def clear_port_cache():
    """Clear port cache - call this when making changes"""
    _port_cache.clear()

class SiteThread(QThread):
    finished = pyqtSignal(str, bool)
    
    def __init__(self, name, base, action, port=None):
        super().__init__()
        self.name = name
        self.base = base
        self.action = action
        self.port = port
    
    def run(self):
        try:
            if self.action == "create": 
                self.create_site()
            elif self.action == "start": 
                self.start_site()
            elif self.action == "archive": 
                self.archive_site()
            elif self.action == "restore": 
                self.restore_site()
        except Exception as e:
            self.finished.emit(str(e), False)

    def create_site(self):
        site_dir = self.base / self.name
        if site_dir.exists():
            self.finished.emit("Site folder already exists", False)
            return
        
        static_dir = site_dir / "static" / "css"
        templates_dir = site_dir / "templates"
        for d in [site_dir, static_dir, templates_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Create CSS file
        (static_dir / "style.css").write_text(
            "body{font-family:'Segoe UI';background:linear-gradient(135deg,#667eea,#764ba2);"
            "margin:0;padding:0;color:#fff;text-align:center;}", 
            encoding="utf-8"
        )
        
        # Create HTML template
        (templates_dir / "index.html").write_text(
            f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.name}</title>
    <link rel='stylesheet' href='{{{{ url_for("static",filename="css/style.css") }}}}'>
</head>
<body>
    <h1>Welcome to {self.name}</h1>
    <p>Flask site running.</p>
</body>
</html>""", 
            encoding="utf-8"
        )
        
        # Create main app
        (site_dir / "app.py").write_text(
            f"""from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port={self.port})
""", 
            encoding="utf-8"
        )
        
        # Create run script
        (site_dir / "run_site.py").write_text(
            f"""import sys
import os
from app import app

if __name__ == '__main__':
    print('Running http://127.0.0.1:{self.port}')
    app.run(debug=True, host='127.0.0.1', port={self.port})
""", 
            encoding="utf-8"
        )
        
        self.finished.emit(f"Site '{self.name}' created at http://127.0.0.1:{self.port}", True)

    def start_site(self):
        run_script = self.base / self.name / "run_site.py"
        if run_script.exists():
            proc = subprocess.Popen(
                [sys.executable, str(run_script)],
                cwd=str(run_script.parent),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.finished.emit(str(proc.pid), True)
        else:
            self.finished.emit("run_site.py not found.", False)

    def archive_site(self):
        site_dir = self.base / self.name
        ARCHIVE_DIR.mkdir(exist_ok=True)
        archive_path = ARCHIVE_DIR / f"{self.name}.zip"
        
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(site_dir):
                for f in files:
                    fp = Path(root) / f
                    z.write(fp, fp.relative_to(site_dir))
        
        shutil.rmtree(site_dir, ignore_errors=True)
        self.finished.emit(f"Archived {self.name}", True)

    def restore_site(self):
        archive_path = ARCHIVE_DIR / f"{self.name}.zip"
        if not archive_path.exists():
            self.finished.emit("Archive not found.", False)
            return
        
        extract_path = BASE_DIR / self.name
        with zipfile.ZipFile(archive_path, 'r') as z:
            extract_path.mkdir(parents=True, exist_ok=True)
            z.extractall(extract_path)
        
        self.finished.emit(f"Restored {self.name}", True)

class Button(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setFixedHeight(42)
        self.setStyleSheet(
            "QPushButton{background:#667eea;color:white;border-radius:6px;font-size:11pt;}"
            "QPushButton:hover{background:#5a6fd8;} "
            "QPushButton:pressed{background:#4c5bc0;} "
            "QPushButton:disabled{background:#cccccc;color:#666666;}"
        )

class FlaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        self.meta = load_metadata()
        self.thread = None
        self._refresh_in_progress = False
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Flask Site Manager")
        self.resize(940, 660)
        w = QWidget()
        self.setCentralWidget(w)
        v = QVBoxLayout(w)
        
        # Header
        header = QLabel("Flask Site Manager", alignment=Qt.AlignCenter)
        header.setStyleSheet("font-size:24px;color:#667eea;font-weight:bold;margin-bottom:10px;")
        v.addWidget(header)
        
        self.tabs = QTabWidget()  # FIX: Make it an instance attribute
        v.addWidget(self.tabs)

        font_css = "font-size:11pt;font-family:'Segoe UI';"

        # --- Create Tab ---
        create_tab = QWidget()
        c_layout = QVBoxLayout(create_tab)
        
        # Input section
        hl = QHBoxLayout()
        label = QLabel("Site Name:")
        label.setStyleSheet(font_css)
        label.setFixedWidth(80)
        hl.addWidget(label)
        
        self.input = QLineEdit()
        self.input.setStyleSheet(f"{font_css} padding:8px;")
        self.input.setPlaceholderText("Enter site name (no spaces)")
        self.input.returnPressed.connect(self.create_site)
        hl.addWidget(self.input)
        c_layout.addLayout(hl)
        
        # Create button
        self.create_btn = Button("Create Site")
        self.create_btn.clicked.connect(self.create_site)
        c_layout.addWidget(self.create_btn)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        c_layout.addWidget(self.progress)
        
        # Log area
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setStyleSheet(f"{font_css} background:#f5f5f5;")
        self.log.setVisible(False)
        c_layout.addWidget(self.log)
        
        self.tabs.addTab(create_tab, "Create")

        # --- Manage Tab ---
        manage_tab = QWidget()
        m_layout = QVBoxLayout(manage_tab)
        
        lbl = QLabel("Active Sites:")
        lbl.setStyleSheet(font_css)
        m_layout.addWidget(lbl)
        
        self.active_list = QListWidget()
        self.active_list.setStyleSheet(f"{font_css} alternate-background-color: #f8f9fa;")
        self.active_list.setAlternatingRowColors(True)
        self.active_list.itemSelectionChanged.connect(self.on_selection_changed)
        m_layout.addWidget(self.active_list)
        
        # Button container
        hl2 = QHBoxLayout()
        self.start_btn = Button("Start")
        self.open_btn = Button("Open Browser")
        self.folder_btn = Button("Open Folder")
        self.archive_btn = Button("Archive")
        self.delete_btn = Button("Delete")
        
        for b in [self.start_btn, self.open_btn, self.folder_btn, self.archive_btn, self.delete_btn]:
            hl2.addWidget(b)
            b.setEnabled(False)
        
        m_layout.addLayout(hl2)
        self.tabs.addTab(manage_tab, "Active Sites")

        # --- Archived Tab ---
        arch_tab = QWidget()
        r_layout = QVBoxLayout(arch_tab)
        
        lbl2 = QLabel("Archived Sites:")
        lbl2.setStyleSheet(font_css)
        r_layout.addWidget(lbl2)
        
        self.arch_list = QListWidget()
        self.arch_list.setStyleSheet(f"{font_css} alternate-background-color: #f8f9fa;")
        self.arch_list.setAlternatingRowColors(True)
        self.arch_list.itemSelectionChanged.connect(self.on_arch_selection_changed)
        r_layout.addWidget(self.arch_list)
        
        hl3 = QHBoxLayout()
        self.restore_btn = Button("Restore")
        self.del_arch_btn = Button("Delete Archive")
        self.restore_btn.setEnabled(False)
        self.del_arch_btn.setEnabled(False)
        hl3.addWidget(self.restore_btn)
        hl3.addWidget(self.del_arch_btn)
        r_layout.addLayout(hl3)
        self.tabs.addTab(arch_tab, "Archived Sites")

        # Connections
        self.start_btn.clicked.connect(self.start_site)
        self.open_btn.clicked.connect(self.open_browser)
        self.folder_btn.clicked.connect(self.open_folder)
        self.archive_btn.clicked.connect(self.archive_site)
        self.delete_btn.clicked.connect(self.delete_site)
        self.restore_btn.clicked.connect(self.restore_site)
        self.del_arch_btn.clicked.connect(self.delete_archive)

        # Optimized timer - less frequent updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(8000)  # Increased from 5s to 8s
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Initial load
        QTimer.singleShot(100, self.load_sites)

    def on_selection_changed(self):
        """Enable/disable buttons based on selection"""
        has_selection = bool(self.active_list.selectedItems())
        for btn in [self.start_btn, self.open_btn, self.folder_btn, self.archive_btn, self.delete_btn]:
            btn.setEnabled(has_selection)

    def on_arch_selection_changed(self):
        """Enable/disable archive buttons based on selection"""
        has_selection = bool(self.arch_list.selectedItems())
        self.restore_btn.setEnabled(has_selection)
        self.del_arch_btn.setEnabled(has_selection)

    def create_site(self):
        name = self.input.text().strip().lower()
        if not name:
            QMessageBox.warning(self, "Invalid", "Please enter a site name.")
            return
        if ' ' in name:
            QMessageBox.warning(self, "Invalid", "Site name cannot contain spaces.")
            return
        if name in self.meta:
            QMessageBox.warning(self, "Exists", "Site already exists.")
            return

        port = get_next_port(self.meta)
        
        self.create_btn.setEnabled(False)
        self.input.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        
        # Clear cache since we're making changes
        clear_port_cache()
        
        self.thread = SiteThread(name, BASE_DIR, "create", port)
        self.thread.finished.connect(lambda msg, ok: self.create_done(name, port, msg, ok))
        self.thread.start()

    def create_done(self, name, port, msg, ok):
        self.create_btn.setEnabled(True)
        self.input.setEnabled(True)
        self.progress.setVisible(False)
        self.input.clear()
        
        if ok:
            self.meta[name] = {"port": port, "pid": None, "status": "Stopped", "archived": False}
            save_metadata(self.meta)
            self.load_sites()
            clear_port_cache()
            # Auto-switch to manage tab
            self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage(f"Site '{name}' created successfully", 3000)
        
        if not ok:
            QMessageBox.critical(self, "Error", msg)

    def load_sites(self):
        """Optimized site loading - only update if changed"""
        current_active = []
        current_archived = []
        
        # Build current state
        for name, data in self.meta.items():
            if data.get("archived"):
                current_archived.append(f"{name} (Archived)")
            else:
                status = "Running" if port_in_use(data["port"]) else "Stopped"
                current_active.append(f"{name} ({status})  http://127.0.0.1:{data['port']}")
        
        # Check if active list needs update
        active_needs_update = False
        if len(current_active) != self.active_list.count():
            active_needs_update = True
        else:
            for i in range(len(current_active)):
                if self.active_list.item(i).text() != current_active[i]:
                    active_needs_update = True
                    break
        
        # Update active list if changed
        if active_needs_update:
            self.active_list.clear()
            for item_text in current_active:
                item = QListWidgetItem(item_text)
                item.setForeground(Qt.green if "Running" in item_text else Qt.gray)
                self.active_list.addItem(item)
        
        # Check if archived list needs update
        archived_needs_update = (len(current_archived) != self.arch_list.count())
        if archived_needs_update:
            self.arch_list.clear()
            for item_text in current_archived:
                item = QListWidgetItem(item_text)
                item.setForeground(Qt.darkMagenta)
                self.arch_list.addItem(item)

    def refresh_status(self):
        """Optimized status refresh with debouncing"""
        if self._refresh_in_progress:
            return
            
        self._refresh_in_progress = True
        changed = False
        
        # Check only non-archived sites
        sites_to_check = {name: data for name, data in self.meta.items() 
                         if not data.get("archived")}
        
        for name, data in sites_to_check.items():
            port = data["port"]
            is_running = port_in_use(port)
            
            if is_running and data["status"] != "Running":
                data["status"] = "Running"
                changed = True
            elif not is_running and data["status"] != "Stopped":
                data["status"] = "Stopped"
                data["pid"] = None
                changed = True
        
        if changed:
            save_metadata(self.meta)
            self.load_sites()
        
        self._refresh_in_progress = False

    def get_selected(self, archived=False):
        lst = self.arch_list if archived else self.active_list
        items = lst.selectedItems()
        if not items:
            QMessageBox.warning(self, "Error", "Please select a site.")
            return None
        return items[0].text().split()[0]

    def start_site(self):
        name = self.get_selected(False)
        if not name: 
            return
            
        if self.meta[name].get("archived"):
            QMessageBox.warning(self, "Archived", "Cannot start archived sites.")
            return
            
        self.statusBar().showMessage(f"Starting {name}...")
        self.thread = SiteThread(name, BASE_DIR, "start")
        self.thread.finished.connect(lambda pid, ok: self.started(name, pid, ok))
        self.thread.start()

    def started(self, name, pid, ok):
        if ok:
            self.meta[name]["pid"] = int(pid)
            self.meta[name]["status"] = "Running"
            save_metadata(self.meta)
            clear_port_cache()
            self.load_sites()
            self.statusBar().showMessage(f"{name} started successfully", 3000)
        else:
            QMessageBox.critical(self, "Error", pid)
            self.statusBar().showMessage(f"Failed to start {name}", 3000)

    def open_browser(self):
        name = self.get_selected(False)
        if not name: 
            return
            
        port = self.meta[name]["port"]
        if port_in_use(port):
            webbrowser.open(f"http://127.0.0.1:{port}")
            self.statusBar().showMessage(f"Opened {name} in browser", 2000)
        else:
            self.statusBar().showMessage(f"Starting {name}...")
            self.thread = SiteThread(name, BASE_DIR, "start")
            self.thread.finished.connect(lambda pid, ok: self.auto_open(name, pid, ok))
            self.thread.start()

    def auto_open(self, name, pid, ok):
        if ok:
            self.meta[name]["pid"] = int(pid)
            self.meta[name]["status"] = "Running"
            save_metadata(self.meta)
            clear_port_cache()
            self.load_sites()
            # Reduced delay
            QTimer.singleShot(800, lambda: webbrowser.open(f"http://127.0.0.1:{self.meta[name]['port']}"))
            self.statusBar().showMessage(f"{name} started and opened in browser", 3000)
        else:
            QMessageBox.critical(self, "Error", f"Failed to start {name}")
            self.statusBar().showMessage(f"Failed to start {name}", 3000)

    def open_folder(self):
        name = self.get_selected(False)
        if not name: 
            return
            
        folder_path = BASE_DIR / name
        if folder_path.exists():
            os.startfile(folder_path)
            self.statusBar().showMessage(f"Opened folder for {name}", 2000)
        else:
            QMessageBox.warning(self, "Error", f"Folder for {name} not found.")

    def archive_site(self):
        name = self.get_selected(False)
        if not name: 
            return
            
        if QMessageBox.question(self, "Confirm Archive", 
                              f"Archive site '{name}'? This will stop the site and compress it.") == QMessageBox.Yes:
            self.statusBar().showMessage(f"Archiving {name}...")
            self.thread = SiteThread(name, BASE_DIR, "archive")
            self.thread.finished.connect(lambda msg, ok: self.archived_done(name, msg, ok))
            self.thread.start()

    def archived_done(self, name, msg, ok):
        if ok:
            self.meta[name]["archived"] = True
            self.meta[name]["status"] = "Archived"
            save_metadata(self.meta)
            clear_port_cache()
            self.load_sites()
            self.statusBar().showMessage(f"Archived {name}", 3000)
        else:
            QMessageBox.critical(self, "Error", msg)
            self.statusBar().showMessage(f"Failed to archive {name}", 3000)

    def restore_site(self):
        name = self.get_selected(True)
        if not name: 
            return
            
        new_port = get_next_port(self.meta)
        self.statusBar().showMessage(f"Restoring {name}...")
        self.thread = SiteThread(name, BASE_DIR, "restore")
        self.thread.finished.connect(lambda msg, ok: self.restored_done(name, new_port, msg, ok))
        self.thread.start()

    def restored_done(self, name, port, msg, ok):
        if ok:
            self.meta[name] = {"port": port, "pid": None, "status": "Stopped", "archived": False}
            save_metadata(self.meta)
            clear_port_cache()
            self.load_sites()
            self.statusBar().showMessage(f"Restored {name}", 3000)
        else:
            QMessageBox.critical(self, "Error", msg)
            self.statusBar().showMessage(f"Failed to restore {name}", 3000)

    def delete_site(self):
        name = self.get_selected(False)
        if not name: 
            return
            
        if QMessageBox.question(self, "Confirm Delete", 
                              f"Permanently delete site '{name}'? This cannot be undone.") == QMessageBox.Yes:
            # Kill process if running
            if port_in_use(self.meta[name]["port"]):
                pid = self.meta[name].get("pid")
                if pid:
                    try:
                        subprocess.run(["taskkill", "/PID", str(pid), "/F"], 
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except:
                        pass
            
            shutil.rmtree(BASE_DIR / name, ignore_errors=True)
            self.meta.pop(name, None)
            save_metadata(self.meta)
            clear_port_cache()
            self.load_sites()
            self.statusBar().showMessage(f"Deleted {name}", 3000)

    def delete_archive(self):
        name = self.get_selected(True)
        if not name: 
            return
            
        if QMessageBox.question(self, "Confirm Delete", 
                              f"Permanently delete archive '{name}'? This cannot be undone.") == QMessageBox.Yes:
            (ARCHIVE_DIR / f"{name}.zip").unlink(missing_ok=True)
            self.meta.pop(name, None)
            save_metadata(self.meta)
            self.load_sites()
            self.statusBar().showMessage(f"Deleted archive {name}", 3000)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = FlaskManager()
    win.show()
    sys.exit(app.exec_())