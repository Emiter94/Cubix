import sys
import json
import os
import subprocess
import uuid
import minecraft_launcher_lib

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QLineEdit, QFrame, QStackedWidget, 
                             QGraphicsOpacityEffect, QProgressBar)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QCursor

CONFIG_FILE = "launcher_profiles.json"
MINECRAFT_DIRECTORY = os.path.join(os.getcwd(), "minecraft")

options = {}

STYLESHEET = """
    QMainWindow { background-color: transparent; }
    
    #CentralContainer {
        background-color: #010A13;
        border-radius: 16px;
        border: 1px solid #2c2c2c;
    }
    
    QLabel { color: #E0E0E0; font-family: 'SF Pro Display Regular', sans-serif; }
    
    QLineEdit, QComboBox {
        background-color: #1c1f20;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 12px;
        font-size: 14px;
        color: #FFF;
    }
    QLineEdit:focus { border: 1px solid #4CAF50; }
    
    /* Скроллбар для выпадающего списка */
    QComboBox QAbstractItemView {
        background-color: #1E1E1E;
        color: #FFF;
        selection-background-color: #4CAF50;
        border: 1px solid #333;
    }

    /* Кнопка запуска */
    QPushButton.actionBtn {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        font-size: 14px;
        padding: 10px;
        border: none;
        border-bottom: 4px solid #388E3C;
    }
    QPushButton.actionBtn:hover {
        background-color: #66BB6A;
        margin-top: 1px;
        border-bottom: 3px solid #388E3C;
    }
    QPushButton.actionBtn:pressed {
        background-color: #2E7D32;
        margin-top: 4px;
        border-bottom: 0px solid #388E3C;
    }
    QPushButton.actionBtn:disabled {
        background-color: #2E5530;
        border-bottom: 4px solid #1B331D;
        color: #888;
    }
    
    /* Mac Buttons */
    QPushButton.macBtn { border-radius: 7px; border: none; }
    QPushButton#btnClose { background-color: #ff5f56; }
    QPushButton#btnClose:hover { background-color: #ff3b30; }
    QPushButton#btnMin { background-color: #ffbd2e; }
    QPushButton#btnMin:hover { background-color: #ffad14; }

    /* Панели */
    #LeftPanel {
        background-color: #101419;
        border-top-left-radius: 16px;
        border-bottom-left-radius: 16px;
    }
    #RightPanel {
        background-color: #010A13;
        border-top-right-radius: 16px;
        border-bottom-right-radius: 16px;
    }
    
    /* Прогресс бар */
    QProgressBar {
        border: none;
        background-color: #1E1E1E;
        height: 6px;
        border-radius: 3px;
        text-align: center;
        color: transparent;
    }
    QProgressBar::chunk {
        background-color: #4CAF50;
        border-radius: 3px;
    }
"""

class VersionThread(QThread):
    versions_loaded = pyqtSignal(list)

    def run(self):
        final_list = []
        
        installed_ids = []
        try:
            installed = minecraft_launcher_lib.utils.get_installed_versions(MINECRAFT_DIRECTORY)
            for v in installed:
                installed_ids.append(v['id'])
                final_list.append(v['id'])
        except Exception as e:
            print(f"Ошибка чтения локальных версий: {e}")

        try:
            remote_list = minecraft_launcher_lib.utils.get_version_list()
            for v in remote_list:
                if v['type'] == 'release' and v['id'] not in installed_ids:
                    final_list.append(v['id'])
                elif v['type'] == 'snapshot' and v['id'] not in installed_ids:
                    final_list.append(v['id'])
        except Exception as e:
            print(f"Ошибка подключения к Mojang: {e}")
        
        ver_list = sorted(final_list, reverse=True)

        self.versions_loaded.emit(ver_list)

class LaunchThread(QThread):
    progress_update = pyqtSignal(int, str)
    state_update = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, username, version):
        super().__init__()
        self.username = username
        self.version = version
        self.mc_dir = MINECRAFT_DIRECTORY

    def run(self):
        def set_status(text): pass
        def set_progress(value, max_value=0):
            if max_value > 0:
                percent = int((value / max_value) * 100)
                self.progress_update.emit(percent, "Downloading...")
            else:
                self.progress_update.emit(0, "Downloading...")

        callback = { "setStatus": set_status, "setProgress": set_progress }

        try:
            self.state_update.emit("CHECKING FILES...")
            minecraft_launcher_lib.install.install_minecraft_version(
                version=self.version,
                minecraft_directory=self.mc_dir,
                callback=callback
            )
            is_installed = True
        except Exception as e:
            print(f"Update failed (Offline mode?): {e}")
            
            version_json = os.path.join(self.mc_dir, "versions", self.version, f"{self.version}.json")
            
            if os.path.exists(version_json):
                self.state_update.emit("OFFLINE MODE...")
                is_installed = True
                
            else:
                self.error_signal.emit("No Internet & Not Installed")
                is_installed = False

        if is_installed:
            try:
                self.state_update.emit("LAUNCHING...")
                options = {
                    "username": self.username,
                    "uuid": str(uuid.uuid1()),
                    "token": "",
                    "launcherName": "CUBIX",
                    "gameDirectory": self.mc_dir,
                    "jvmArguments": [
                            "-javaagent:online_fix.jar=ely.by"
                            "-Xmx10G -Xms10G"
                        ]
                }
                
                command = minecraft_launcher_lib.command.get_minecraft_command(
                    version=self.version,
                    minecraft_directory=self.mc_dir,
                    options=options
                )

                subprocess.Popen(command)
                self.finished_signal.emit()
                
            except Exception as e:
                self.error_signal.emit(f"Launch Error: {str(e)}")

class MinecraftLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(750, 420)
        self.old_pos = None
        self.user_data = self.load_config()

        

        if not os.path.exists(MINECRAFT_DIRECTORY):
            try: os.makedirs(MINECRAFT_DIRECTORY)
            except: pass

        self.init_ui()

        if not self.user_data.get("username"):
            self.stack.setCurrentIndex(0)
            self.fade_in_widget(self.page_register)
        else:
            self.lbl_welcome_name.setText(self.user_data.get("username"))
            self.stack.setCurrentIndex(1)
            self.fade_in_widget(self.page_splash)
            QTimer.singleShot(2000, self.transition_to_main)
            
        self.load_versions_background()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_config(self, username, last_version=None):
        data = self.user_data
        data["username"] = username
        if last_version:
            data["last_version"] = last_version
            
        with open(CONFIG_FILE, "w") as f: json.dump(data, f)
        self.user_data = data

    def init_ui(self):
        self.central_container = QWidget()
        self.central_container.setObjectName("CentralContainer")
        self.setCentralWidget(self.central_container)
        self.setStyleSheet(STYLESHEET)
        
        layout = QVBoxLayout(self.central_container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.page_register = QWidget()
        self.setup_register_ui()
        self.stack.addWidget(self.page_register)

        self.page_splash = QWidget()
        self.setup_splash_ui()
        self.stack.addWidget(self.page_splash)

        self.page_main = QWidget()
        self.setup_main_ui()
        self.stack.addWidget(self.page_main)

    def setup_register_ui(self):
        layout = QVBoxLayout(self.page_register)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl = QLabel("Welcome to CUBIX Launcher")
        lbl.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        sub = QLabel("Let's set up your profile.")
        sub.setStyleSheet("color: #888; font-size: 14px; margin-bottom: 20px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.reg_input = QLineEdit()
        self.reg_input.setPlaceholderText("Enter your username")
        self.reg_input.setFixedWidth(300)
        self.reg_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn = QPushButton("CREATE PROFILE")
        btn.setProperty("class", "actionBtn")
        btn.setFixedWidth(200)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.clicked.connect(self.action_register)
        
        layout.addWidget(lbl)
        layout.addWidget(sub)
        layout.addWidget(self.reg_input, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def setup_splash_ui(self):
        layout = QVBoxLayout(self.page_splash)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl = QLabel("Welcome back")
        lbl.setStyleSheet("color: #888; font-size: 18px; font-weight: 300;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_welcome_name = QLabel("Username")
        self.lbl_welcome_name.setStyleSheet("font-size: 32px; font-weight: bold; color: #4CAF50; margin-top: 5px;")
        self.lbl_welcome_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(lbl)
        layout.addWidget(self.lbl_welcome_name)

    def setup_main_ui(self):
        h_layout = QHBoxLayout(self.page_main)
        h_layout.setContentsMargins(0,0,0,0)
        h_layout.setSpacing(0)
        
        left = QFrame()
        left.setObjectName("LeftPanel")
        l_lay = QVBoxLayout(left)
        logo = QLabel("CUBIX")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size: 28px; font-weight: 900; letter-spacing: 2px;")
        l_lay.addStretch(); l_lay.addWidget(logo); l_lay.addStretch()
        
        right = QFrame()
        right.setObjectName("RightPanel")
        r_lay = QVBoxLayout(right)
        
        r_lay.setContentsMargins(30, 20, 20, 30)
        
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        for name, func in [("btnClose", self.close), ("btnMin", self.showMinimized)]:
            b = QPushButton()
            b.setFixedSize(14, 14); b.setObjectName(name); b.setProperty("class", "macBtn")
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            if func: b.clicked.connect(func)
            top_bar.addWidget(b); top_bar.addSpacing(6)
        r_lay.addLayout(top_bar)
        
        r_lay.addStretch()
        
        self.main_username = QLabel()
        self.main_username.setStyleSheet("font-size: 20px; font-weight: bold;")
        r_lay.addWidget(self.main_username)
        
        self.ver_combo = QComboBox()
        self.ver_combo.addItem("Loading versions...")
        r_lay.addWidget(self.ver_combo)
        r_lay.addSpacing(15)
        
        self.play_btn = QPushButton("LAUNCH GAME")
        self.play_btn.setProperty("class", "actionBtn")
        self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.play_btn.setFixedHeight(45)
        self.play_btn.clicked.connect(self.launch_game)
        self.play_btn.setEnabled(False) 
        r_lay.addWidget(self.play_btn)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        r_lay.addWidget(self.progress_bar)
        
        r_lay.addStretch()
        h_layout.addWidget(left, 40)
        h_layout.addWidget(right, 60)

    def load_versions_background(self):
        self.ver_thread = VersionThread()
        self.ver_thread.versions_loaded.connect(self.update_version_list)
        self.ver_thread.start()

    def update_version_list(self, versions):
        self.ver_combo.clear()
        if not versions:
            self.ver_combo.addItem("you dont have any versions and internet access(")
        else:
            self.ver_combo.addItems(versions)
        
        last_ver = self.user_data.get("last_version")
        if last_ver:
            index = self.ver_combo.findText(last_ver)
            if index != -1:
                self.ver_combo.setCurrentIndex(index)
        
        self.play_btn.setEnabled(True)

    def launch_game(self):
        self.play_btn.setEnabled(False)
        self.ver_combo.setEnabled(False)
        self.play_btn.setText("STARTING...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        username = self.user_data.get("username", "Steve")
        version = self.ver_combo.currentText()
        
        self.save_config(username, version)
        
        self.thread = LaunchThread(username, version)
        self.thread.state_update.connect(self.update_launch_state)
        self.thread.progress_update.connect(self.update_progress)
        self.thread.finished_signal.connect(self.launch_finished)
        self.thread.error_signal.connect(self.launch_error)
        self.thread.start()

    def update_launch_state(self, state):
        self.play_btn.setText(state)

    def update_progress(self, percent, text):
        self.progress_bar.setValue(percent)

    def launch_finished(self):
        self.play_btn.setText("LAUNCHED")
        self.progress_bar.setVisible(False)
        self.play_btn.setEnabled(True)
        self.ver_combo.setEnabled(True)
        self.play_btn.setText("LAUNCH GAME")

    def launch_error(self, err_msg):
        self.play_btn.setText("ERROR")
        self.play_btn.setEnabled(True)
        self.ver_combo.setEnabled(True)
        print(f"Error: {err_msg}")

    def action_register(self):
        name = self.reg_input.text().strip()
        if not name: return
        self.save_config(name)
        self.transition_to_main()

    def transition_to_main(self):
        self.main_username.setText(self.user_data.get("username", "Player"))
        self.fade_switch_page(self.page_main)

    def fade_in_widget(self, widget):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(800)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()
        self.active_anim = anim 

    def fade_switch_page(self, new_widget):
        current_widget = self.stack.currentWidget()
        self.eff_out = QGraphicsOpacityEffect(current_widget)
        current_widget.setGraphicsEffect(self.eff_out)
        self.anim_out = QPropertyAnimation(self.eff_out, b"opacity")
        self.anim_out.setDuration(500)
        self.anim_out.setStartValue(1)
        self.anim_out.setEndValue(0)
        self.anim_out.finished.connect(lambda: self._finish_switch(new_widget))
        self.anim_out.start()

    def _finish_switch(self, new_widget):
        self.stack.setCurrentWidget(new_widget)
        self.eff_in = QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(self.eff_in)
        self.anim_in = QPropertyAnimation(self.eff_in, b"opacity")
        self.anim_in.setDuration(800)
        self.anim_in.setStartValue(0)
        self.anim_in.setEndValue(1)
        self.anim_in.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event):
        self.old_pos = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MinecraftLauncher()
    win.show()
    sys.exit(app.exec())