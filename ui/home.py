from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QLineEdit, QMessageBox, QHBoxLayout, QGraphicsDropShadowEffect
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
        self.setWindowIcon(QIcon(r"C:\Users\Islam\Desktop\descktopJbonus\assets\banners\icons\image.png"))

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
                background-color: #A3D80D;
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
            QLineEdit {
                background: #F5F5F5;
                color: #212121;
                border: 2px solid #AED581;
                border-radius: 10px;
                padding: 10px;
                font-size: 16px;
                font-family: 'Nunito', 'Segoe UI', 'Roboto', sans-serif;
            }
            QLineEdit:focus {
                border: 2px solid #7CB342;
                background: #FFFFFF;
            }
        """)

        header = QHBoxLayout()
        header.setContentsMargins(5, 5, 5, 0)
        header.setSpacing(20)

        logo = QLabel()
        logo_path = os.path.join("assets", "banners", "icons", "image.png")
        pix = QPixmap(logo_path)
        if pix.isNull():
            pix = QPixmap(80, 80)
            pix.fill(QColor("#A3D80D"))
        else:
            pix = pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setPixmap(pix)
        logo.setFixedSize(80, 80)
        header.addWidget(logo, alignment=Qt.AlignVCenter | Qt.AlignLeft)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        self.time_label = QLabel("--:--")
        self.time_label.setFont(QFont("Nunito", 28, QFont.Bold))
        self.time_label.setAlignment(Qt.AlignCenter)
        self.date_label = QLabel("-- -- ----")
        self.date_label.setFont(QFont("Nunito", 11))
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("color:#BDBDBD;")
        center_layout.addWidget(self.time_label)
        center_layout.addWidget(self.date_label)
        header.addWidget(center, stretch=1, alignment=Qt.AlignVCenter | Qt.AlignHCenter)

        support = QWidget()
        support_layout = QVBoxLayout(support)
        support_layout.setContentsMargins(0, 0, 0, 0)
        support_layout.setSpacing(0)
        support_label = QLabel("Поддержка:")
        support_label.setFont(QFont("Nunito", 11))
        support_label.setAlignment(Qt.AlignRight)
        phone_label = QLabel("0 (700) 000 000")
        phone_label.setFont(QFont("Nunito", 13, QFont.Bold))
        phone_label.setStyleSheet("color:#A3D80D;")
        phone_label.setAlignment(Qt.AlignRight)
        support_layout.addWidget(support_label)
        support_layout.addWidget(phone_label)
        header.addWidget(support, alignment=Qt.AlignVCenter | Qt.AlignRight)

        self.layout.addLayout(header)
        self.layout.addSpacing(8)

        self.ad_label = QLabel(alignment=Qt.AlignCenter)
        self.ad_label.setMinimumHeight(650)
        self.layout.addWidget(self.ad_label)

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

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("🔍 Сканируйте штрихкод")
        self.barcode_input.setClearButtonEnabled(True)
        self.barcode_input.returnPressed.connect(self.submit_material)
        self.barcode_input.hide()
        self.layout.addWidget(self.barcode_input)

        self.confirm_btn = QPushButton("✅ Подтвердить")
        self.confirm_btn.setIcon(QIcon("assets/icons/check.png"))
        self.confirm_btn.setIconSize(QSize(24, 24))
        self.confirm_btn.clicked.connect(self.submit_material)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.hide()
        self.layout.addWidget(self.confirm_btn)

        self.info_label = QLabel(alignment=Qt.AlignCenter)
        self.info_label.hide()
        self.layout.addWidget(self.info_label)

        self.start_btn = QPushButton("Нажмите 'Начать', чтобы сдать вторсырьё")
        self.start_btn.setIcon(QIcon("assets/icons/start.png"))
        self.start_btn.setIconSize(QSize(24, 24))
        self.start_btn.setFont(QFont("Nunito", 15, QFont.Bold))
        self.start_btn.clicked.connect(self.start_session)
        self.layout.addWidget(self.start_btn)

        self.back_btn = QPushButton("⬅ Назад")
        self.back_btn.setFont(QFont("Nunito", 14, QFont.Bold))
        self.back_btn.setStyleSheet(
            "background-color: #eee; color: #444; border-radius: 12px; padding: 10px; margin-top: 10px;")
        self.back_btn.clicked.connect(self.reset_to_home)
        self.back_btn.hide()
        self.layout.addWidget(self.back_btn)

    def connect_signals(self):
        self.material_sent.connect(self.on_material_sent)
        self.cap_accepted_signal.connect(self.on_cap_received)

    def update_time(self):
        from datetime import datetime
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M"))
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        self.date_label.setText(f"{now.day} {months[now.month-1]} {now.year}")

    def load_banners(self):
        path = os.path.join("assets", "banners")
        if os.path.exists(path):
            self.banner_urls = [os.path.join(path, f) for f in os.listdir(path)
                                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
            if self.banner_urls:
                self.show_banner(self.banner_urls[0])
                self.banner_timer = QTimer(self)
                self.banner_timer.timeout.connect(self.next_banner)
                self.banner_timer.start(5000)

    def show_banner(self, path):
        pixmap = load_image_from_file(path)
        if pixmap:
            self.loaded_pixmap = pixmap
            self.ad_label.setPixmap(
                pixmap.scaled(
                    self.ad_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )
            anim = QPropertyAnimation(self.ad_label, b"windowOpacity")
            anim.setDuration(500)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.InOutQuad)
            anim.start()
            self.anim = anim

    def next_banner(self):
        if self.banner_urls:
            self.current_banner_index = (self.current_banner_index + 1) % len(self.banner_urls)
            self.show_banner(self.banner_urls[self.current_banner_index])

    def show_loading_overlay(self):
        if self.loading_overlay:
            return
        self.loading_overlay = QWidget(self)
        self.loading_overlay.setGeometry(0, 0, self.width(), self.height())
        self.loading_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.loading_overlay.setAttribute(Qt.WA_DeleteOnClose)
        self.loading_overlay.show()
        layout = QVBoxLayout(self.loading_overlay)
        layout.setAlignment(Qt.AlignCenter)
        svg_path = os.path.join("assets", "banners", "icons", "5.svg")
        svg_widget = QSvgWidget(svg_path)
        svg_widget.setFixedSize(120, 120)
        layout.addWidget(svg_widget)

    def hide_loading_overlay(self):
        if self.loading_overlay:
            self.loading_overlay.deleteLater()
            self.loading_overlay = None

    def show_status(self, text):
        self.status_indicator.setToolTip(text)
        self.status_gif.start()
        self.status_indicator.setVisible(True)

    def hide_status(self):
        self.status_gif.stop()
        self.status_indicator.setVisible(False)

    def on_connection_state_changed(self, is_connected):
        if is_connected:
            self.status_indicator.setToolTip("🟢 Подключено к серверу")
        else:
            self.status_indicator.setToolTip("🔴 Нет подключения к серверу")

    def check_socket_and_show_qr(self):
        print("== check_socket_and_show_qr, socket_ready =", self.socket_ready)
        self.hide_loading_overlay()
        self.show_qr_code()

    def on_socket_opened(self):
        print("🧠 Socket открыт, запускаем задержку перед показом QR")
        self.session_active = True
        QTimer.singleShot(1000, self.check_socket_and_show_qr)  # 1 секунда для теста

    def show_qr_code(self):
        print("== SHOW QR CODE ==")
        if self.qr_shown:
            print("QR уже показан!")
            return
        self.qr_shown = True

        path = generate_qr(FANDOMAT_TOKEN)
        print("QR path generated:", path)
        if not os.path.exists(path):
            print("QR file not found!!")
        qr_pixmap = QPixmap(path).scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.qr_label.setPixmap(qr_pixmap)
        self.qr_label.show()

        # shadow = QGraphicsDropShadowEffect()
        # shadow.setBlurRadius(40)
        # shadow.setXOffset(0)
        # shadow.setYOffset(8)
        # shadow.setColor(QColor(80, 80, 80, 180))
        # self.qr_label.setGraphicsEffect(shadow)

        self.qr_hint_label.show()
        self.ad_label.hide()
        self.start_btn.hide()
        self.back_btn.show()
        self.status_indicator.setVisible(False)
        self.hide_loading_overlay()

    def start_session(self):
        if self.session_active:
            print("⚠️ Сессия уже активна. Новая не будет запущена.")
            return
        print("▶️ Нажата кнопка 'Начать приём'")
        self.session_active = True
        self.socket_ready = False
        self.qr_shown = False
        self.start_btn.hide()
        self.back_btn.show()
        self.qr_label.hide()
        self.qr_label.setGraphicsEffect(None)
        self.qr_hint_label.hide()
        self.status_indicator.setToolTip("🔄 Подключение к WebSocket...")
        self.status_gif.start()
        self.status_indicator.setVisible(True)
        if self.ws_worker:
            WebSocketManager().stop()
            self.ws_worker = None
            QTimer.singleShot(2000, self._start_ws)
        else:
            self._start_ws()

    def _start_ws(self):
        self.ws_worker = WebSocketManager().start_worker()
        self.ws_worker.connected.connect(self.on_ws_connected)
        self.ws_worker.cap_accepted_signal.connect(self.cap_accepted_signal)
        self.ws_worker.session_ended.connect(self.on_session_ended)
        self.ws_worker.error.connect(lambda msg: self.show_status(f"❌ WebSocket ошибка: {msg}"))
        self.ws_worker.connected_state_changed.connect(self.on_connection_state_changed)
        self.ws_worker.socket_opened.connect(self.on_socket_opened)
        self.show_loading_overlay()

    def on_ws_connected(self, user):
        self.hide_status()
        self.ad_label.hide()
        self.qr_label.hide()
        self.qr_hint_label.hide()
        self.start_btn.hide()
        self.back_btn.show()
        full_name = user.get("get_full_name") or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        quantity = user.get("quantity_of_raw_materials", 0.0)
        self.barcode_input.show()
        self.confirm_btn.show()
        self.confirm_btn.setEnabled(True)
        self.info_label.hide()
        self.barcode_input.setFocus()

    def on_session_ended(self):
        self.show_loading_overlay()
        QTimer.singleShot(1500, self._reset_after_disconnect)

    def _reset_after_disconnect(self):
        self.hide_loading_overlay()
        self.reset_to_home()

    def reset_to_home(self):
        print("== RESET TO HOME ==")
        self.qr_shown = False 
        self.start_btn.setText("Нажмите 'Начать', чтобы сдать вторсырьё")
        self.qr_label.clear()
        self.qr_label.hide()
        self.qr_label.setGraphicsEffect(None)
        self.qr_hint_label.hide()
        self.barcode_input.hide()
        self.confirm_btn.hide()
        self.info_label.hide()
        self.barcode_input.clear()
        self.ad_label.show()
        self.hide_status()
        self.cap_required = False
        self.cap_received = False
        self.confirm_btn.setEnabled(False)
        self.session_active = False
        self.start_btn.show()
        self.back_btn.hide()
        WebSocketManager().stop()
        self.ws_worker = None

    def on_cap_received(self):
        self.cap_received = True
        QMessageBox.information(self, "Крышка", "Крышка принята. Теперь сдайте бутылку.")

    def submit_material(self):
        barcode = self.barcode_input.text().strip()
        if not barcode.isdigit():
            self.barcode_input.setStyleSheet("border: 2px solid red;")
            QTimer.singleShot(1500, lambda: self.barcode_input.setStyleSheet(""))
            QMessageBox.warning(self, "Неверный ввод", "Введите корректный штрихкод")
            return
        try:
            r = requests.get(f"{API_BASE_URL}/recyclable-materials/by/barcode/{barcode}/", timeout=5)
            r.raise_for_status()
            data = r.json()
            name = data.get("name", "Неизвестно")
            mtype = data.get("type", "")
            weight = data.get("weight", 0)
            self.info_label.setText(f"Материал: {name}\nТип: {mtype}\nВес: {weight} г")
            self.info_label.setStyleSheet("color: white;")
            self.info_label.show()
            if mtype == "plastic" and not self.cap_received:
                self.cap_required = True
                self.barcode_input.clear()
                return
            self.ws_worker.send_material(barcode)
            self.material_sent.emit(name)
        except requests.RequestException as ex:
            QMessageBox.critical(self, "Ошибка сети", f"Нет соединения с сервером!\n\n{ex}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def on_material_sent(self, name):
        self.info_label.setStyleSheet("color: #00E676; font-weight: bold")
        self.info_label.setText(f"✅ {name} успешно отправлен!")
        self.barcode_input.clear()

    def resizeEvent(self, event):
        if self.loaded_pixmap:
            self.ad_label.setPixmap(
                self.loaded_pixmap.scaled(
                    self.ad_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )
        return super().resizeEvent(event)
