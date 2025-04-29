from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QLineEdit
)
from PyQt5.QtGui import QPixmap, QFont, QIcon, QMovie, QColor, QFontDatabase
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
import os
import requests
from utils.qr_generator import generate_qr
from utils.image_loader import load_image_from_file
from ws.manager import WebSocketManager
from PyQt5.QtSvg import QSvgWidget

FANDOMAT_TOKEN = "fan_bc539aed70f65db5544c5f38ec1a076250150a7802f341d9fa94729a32bc9c5c"
API_BASE_URL = "https://back.jashyl-bonus.kg/api/v1"

class HomeScreen(QWidget):
    material_sent = pyqtSignal(str)
    cap_accepted_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Фандомат")
        self.setMinimumSize(380, 500)
        self.resize(600, 900)
        self.setWindowIcon(QIcon("assets/banners/icons/image.png"))

        QFontDatabase.addApplicationFont("assets/fonts/Nunito-Italic-VariableFont_wght.ttf")
        QFontDatabase.addApplicationFont("assets/fonts/Nunito-VariableFont_wght.ttf")
        self.setFont(QFont("Nunito", 11))

        self.cap_required = False
        self.cap_received = False
        self.ws_worker = None
        self.banner_urls = []
        self.current_banner_index = 0
        self.loaded_pixmap = None
        self.socket_ready = False
        self.loading_overlay = None
        self.qr_shown = False
        self.session_active = False
        self.session_stage = "waiting_barcode"
        self.barcode_buffer = ""
        self.scanned_barcode = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)

        self.setup_ui()
        self.connect_signals()

        QTimer.singleShot(100, self.load_banners)
        self.show()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.update_time)
        self._clock_timer.start(1000)
        self.update_time()

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key_Return, Qt.Key_Enter]:
            code = self.barcode_buffer.strip()
            self.barcode_buffer = ""
            if code:
                self.handle_scanned_code(code)
        else:
            self.barcode_buffer += event.text()

    def handle_scanned_code(self, code):
        if self.session_stage == "waiting_barcode":
            self.process_material_scan(code)
        elif self.session_stage == "waiting_bottle_barcode":
            self.process_bottle_verification(code)

    def process_material_scan(self, barcode):
        self.scanned_barcode = barcode
        try:
            r = requests.get(f"{API_BASE_URL}/recyclable-materials/by/barcode/{barcode}/", timeout=5)
            r.raise_for_status()
            data = r.json()
            mtype = data.get("type")
            self.show_success_animation()

            if mtype == "plastic":
                self.session_stage = "waiting_cap"
                self.send_arduino_command("on_cap")
                self.show_waiting_cap_animation()
            else:
                if self.ws_worker:
                    self.ws_worker.send_material(barcode)
                self.material_sent.emit(data.get("name", "Материал"))
        except Exception as e:
            self.show_error_animation()

    def process_bottle_verification(self, barcode):
        if barcode == self.scanned_barcode:
            self.send_arduino_command("accept_bottle")
            self.show_success_animation()
            self.session_stage = "waiting_bottle_accept"
        else:
            self.send_arduino_command("reject_bottle")
            self.show_error_animation()

    def on_cap_received(self):
        self.cap_received = True
        self.show_success_animation()
        QTimer.singleShot(1000, self.open_bottle_stage)

    def open_bottle_stage(self):
        self.send_arduino_command("open_bottle")
        self.session_stage = "waiting_bottle_barcode"

    def on_bottle_accepted(self):
        self.show_success_animation()
        QTimer.singleShot(2000, self.reset_to_home)

    def send_arduino_command(self, command):
        if self.ws_worker and self.ws_worker.arduino:
            try:
                self.ws_worker.arduino.write((command + "\n").encode())
            except Exception as e:
                print(f"Ошибка отправки в Arduino: {e}")

    def show_success_animation(self):
        self.ad_label.setMovie(QMovie("assets/icons/success.gif"))
        self.ad_label.movie().start()

    def show_error_animation(self):
        self.ad_label.setMovie(QMovie("assets/icons/error.gif"))
        self.ad_label.movie().start()

    def show_waiting_cap_animation(self):
        self.ad_label.setMovie(QMovie("assets/icons/waiting_cap.gif"))
        self.ad_label.movie().start()

    def reset_to_home(self):
        self.session_stage = "waiting_barcode"
        self.cap_received = False
        self.start_btn.show()
        self.back_btn.hide()
        self.load_banners()

    def update_time(self):
        from datetime import datetime
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M"))
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        self.date_label.setText(f"{now.day} {months[now.month-1]} {now.year}")

    # ➡ дальше весь твой код setup_ui, connect_signals, load_banners и т.д.
    def setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                color: #212121;
                font-family: 'Nunito', 'Segoe UI', 'Roboto', sans-serif;
            }
            QLabel {
                color: #333333;
                font-family: 'Nunito', 'Segoe UI', 'Roboto', sans-serif;
            }
            QPushButton {
                background-color: #3D9A32;
                color: #fff;
                font-size: 18px;
                font-weight: bold;
                padding: 14px 0;
                border: none;
                border-radius: 12px;
                font-family: 'Nunito', 'Segoe UI', 'Roboto', sans-serif;
            }
            QPushButton:hover {
                background-color: #97c40a;
            }
            QPushButton:pressed {
                background-color: #7fc300;
            }
        """)

        # ------------------- HEADER -------------------
        header_widget = QWidget()
        header_widget.setFixedHeight(160)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(30, 30, 30, 30)
        header_layout.setSpacing(20)

        # Logo
        logo = QSvgWidget(os.path.join("assets", "banners", "icons", "Group 7 (1).svg"))
        logo.setFixedSize(120, 120)
        header_layout.addWidget(logo, alignment=Qt.AlignVCenter | Qt.AlignLeft)

        # Clock
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        self.time_label = QLabel("--:--")
        self.time_label.setFont(QFont("Nunito", 36, QFont.Bold))
        self.time_label.setAlignment(Qt.AlignCenter)
        self.date_label = QLabel("-- -- ----")
        self.date_label.setFont(QFont("Nunito", 18))
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("color:#BDBDBD;")
        center_layout.addWidget(self.time_label)
        center_layout.addWidget(self.date_label)
        header_layout.addWidget(center, stretch=1, alignment=Qt.AlignVCenter | Qt.AlignHCenter)

        # Support
        support = QWidget()
        support_layout = QVBoxLayout(support)
        support_layout.setContentsMargins(0, 0, 0, 0)
        support_layout.setSpacing(0)
        support_label = QLabel("Поддержка:")
        support_label.setFont(QFont("Nunito", 20))
        support_label.setAlignment(Qt.AlignRight)
        phone_label = QLabel("0 (700) 000 000")
        phone_label.setFont(QFont("Nunito", 20, QFont.Bold))
        phone_label.setStyleSheet("color:#3D9A32;")
        phone_label.setAlignment(Qt.AlignRight)
        support_layout.addWidget(support_label)
        support_layout.addWidget(phone_label)
        header_layout.addWidget(support, alignment=Qt.AlignVCenter | Qt.AlignRight)

        self.layout.addWidget(header_widget)
        self.layout.addSpacing(8)

        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #E0E0E0; margin-bottom: 0px;")
        self.layout.addWidget(line)

        # ------------------- BANNER / QR -------------------
        banner_container = QWidget()
        banner_layout = QVBoxLayout(banner_container)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        banner_layout.setSpacing(0)
        banner_layout.setAlignment(Qt.AlignCenter)

        self.ad_label = QLabel(alignment=Qt.AlignCenter)
        self.ad_label.setMinimumSize(900, 900)
        self.ad_label.setScaledContents(True)
        banner_layout.addWidget(self.ad_label)

        self.layout.addWidget(banner_container, stretch=1)

        self.status_indicator = QLabel("", alignment=Qt.AlignCenter)
        self.status_indicator.setVisible(False)
        self.status_gif = QMovie("assets/icons/loading.gif")
        self.status_indicator.setMovie(self.status_gif)
        self.layout.addWidget(self.status_indicator)

        self.qr_label = QLabel(alignment=Qt.AlignCenter)
        self.qr_label.hide()
        self.layout.addWidget(self.qr_label)

        self.qr_hint_label = QLabel(
            "Отсканируйте QR-код своим приложением для начала сдачи сырья",
            alignment=Qt.AlignCenter
        )
        self.qr_hint_label.setFont(QFont("Nunito", 14, QFont.Bold))
        self.qr_hint_label.setStyleSheet("color:#212121; margin-top: 10px;")
        self.qr_hint_label.setWordWrap(True)
        self.qr_hint_label.hide()
        self.layout.addWidget(self.qr_hint_label)

        self.info_label = QLabel(alignment=Qt.AlignCenter)
        self.info_label.hide()
        self.layout.addWidget(self.info_label)

        # ------------------- BUTTONS (Start / Back) -------------------
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 40)
        buttons_layout.setSpacing(10)
        buttons_layout.setAlignment(Qt.AlignBottom)

        self.start_btn = QPushButton("Нажмите 'Начать', чтобы сдать вторсырьё")
        self.start_btn.setIcon(QIcon("assets/icons/start.png"))
        self.start_btn.setIconSize(QSize(24, 24))
        self.start_btn.setFont(QFont("Nunito", 15, QFont.Bold))
        self.start_btn.clicked.connect(self.start_session)
        buttons_layout.addWidget(self.start_btn)

        self.back_btn = QPushButton("⬅ Назад")
        self.back_btn.setFont(QFont("Nunito", 14, QFont.Bold))
        self.back_btn.setStyleSheet(
            "background-color: #eee; color: #444; border-radius: 12px; padding: 10px; margin-top: 10px;"
        )
        self.back_btn.clicked.connect(self.reset_to_home)
        self.back_btn.hide()
        buttons_layout.addWidget(self.back_btn)

        self.layout.addWidget(buttons_widget)
