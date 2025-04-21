from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QLineEdit, QMessageBox, QHBoxLayout, QSpacerItem, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QFont, QIcon, QMovie
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
        self.setFixedSize(420, 700)
        self.setWindowIcon(QIcon("assets/icons/recycle.png"))

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




        self.setup_ui()
        QTimer.singleShot(100, self.load_banners)
        self.show()

    def setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.92); /* Полупрозрачный светлый фон */
                color: #212121;
                font-family: 'Segoe UI', 'Roboto', sans-serif;
            }

            QLabel {
                font-size: 17px;
                color: #333333;
            }

            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 18px;
                padding: 12px 20px;
                border: none;
                border-radius: 12px;
            }

            QPushButton:hover {
                background-color: #66BB6A;
            }

            QPushButton:pressed {
                background-color: #388E3C;
            }

            QLineEdit {
                background: #F5F5F5;
                color: #212121;
                border: 2px solid #AED581;
                border-radius: 10px;
                padding: 10px;
                font-size: 16px;
            }

            QLineEdit:focus {
                border: 2px solid #7CB342;
                background: #FFFFFF;
            }
        """)


        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)

        self.ad_label = QLabel(alignment=Qt.AlignCenter)
        self.ad_label.setScaledContents(True)
        self.layout.addWidget(self.ad_label)

        self.status_indicator = QLabel("", alignment=Qt.AlignCenter)
        self.status_indicator.setVisible(False)
        self.status_gif = QMovie("assets/icons/loading.gif")
        self.status_indicator.setMovie(self.status_gif)
        self.layout.addWidget(self.status_indicator)

        self.title = QLabel("Нажмите 'Начать', чтобы сдать вторсырьё", alignment=Qt.AlignCenter)
        self.title.setWordWrap(True)
        self.title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.layout.addWidget(self.title)

        self.qr_label = QLabel(alignment=Qt.AlignCenter)
        self.qr_label.hide()
        self.layout.addWidget(self.qr_label)

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

        self.start_btn = QPushButton("🚀 Начать приём")
        self.start_btn.setIcon(QIcon("assets/icons/start.png"))
        self.start_btn.setIconSize(QSize(24, 24))
        self.start_btn.clicked.connect(self.start_session)
        self.layout.addWidget(self.start_btn)

        self.material_sent.connect(self.on_material_sent)
        self.cap_accepted_signal.connect(self.on_cap_received)
    
    def show_loading_overlay(self):
        if self.loading_overlay:
            return

        self.loading_overlay = QWidget(self)
        # self.loading_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        self.loading_overlay.setGeometry(0, 0, self.width(), self.height())
        self.loading_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.loading_overlay.setAttribute(Qt.WA_DeleteOnClose)
        self.loading_overlay.show()

        layout = QVBoxLayout(self.loading_overlay)
        layout.setAlignment(Qt.AlignCenter)

        svg_path = r"C:\Users\Islam\Desktop\descktopJbonus\assets\banners\icons\5.svg"  # путь до твоего SVG
        svg_widget = QSvgWidget(svg_path)
        svg_widget.setFixedSize(120, 120)

        layout.addWidget(svg_widget)


    def check_socket_and_show_qr(self):
        self.hide_loading_overlay()
        if self.socket_ready:
            self.show_qr_code()


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

    def reset_to_home(self):
        self.title.setText("Нажмите 'Начать', чтобы сдать вторсырьё")
        self.qr_label.clear()
        self.qr_label.hide()
        self.barcode_input.hide()
        self.confirm_btn.hide()
        self.info_label.hide()
        self.barcode_input.clear()
        self.start_btn.setEnabled(True)  # ✅ снова разрешаем нажимать
        self.start_btn.show()
        self.ad_label.show()
        self.hide_status()
        self.cap_required = False
        self.cap_received = False
        self.confirm_btn.setEnabled(False)
        self.session_active = False


        WebSocketManager().stop()
        self.ws_worker = None  # 🔥 Обнуляем

        
    def _reset_after_disconnect(self):
        self.hide_loading_overlay()
        self.reset_to_home()

    def on_session_ended(self):
        self.show_loading_overlay()  # ⏳ Показать загрузку
        self.title.setText("🔌 Клиент отключился, возвращаемся...")

        QTimer.singleShot(1500, self._reset_after_disconnect)  # ⏱ Через 2 сек вернуть на домашний



    def resizeEvent(self, event):
        if self.loaded_pixmap:
            self.ad_label.setPixmap(self.loaded_pixmap.scaled(
                self.ad_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def load_banners(self):
        path = "assets/banners"
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
            self.ad_label.setPixmap(pixmap.scaled(
                self.ad_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
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
            
    def on_socket_opened(self):
        print("🧠 Socket открыт, запускаем задержку перед показом QR")
        self.socket_ready = True
        QTimer.singleShot(4700, self.check_socket_and_show_qr)


            
    def show_qr_code(self):
        if self.qr_shown:  # 🧠 уже показан — не повторяем
            return
        self.qr_shown = True

        path = generate_qr(FANDOMAT_TOKEN)
        self.qr_label.setPixmap(QPixmap(path).scaled(220, 220, Qt.KeepAspectRatio))
        self.qr_label.show()
        self.title.setText("📲 Отсканируйте QR-код в приложении")
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
        self.qr_label.hide()
        self.title.setText("🟡 Ожидание подключения клиента...\n⏳ Устанавливаем соединение с сервером...")

        self.status_indicator.setToolTip("🔄 Подключение к WebSocket...")
        self.status_gif.start()
        self.status_indicator.setVisible(True)

        # 🛑 Надёжно останавливаем предыдущий worker (если он есть)
        if self.ws_worker:
            WebSocketManager().stop()
            self.ws_worker = None
            QTimer.singleShot(2000, self._start_ws)  # ⏳ ждём, чтобы сокет точно закрылся
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
        full_name = user.get("get_full_name") or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        quantity = user.get("quantity_of_raw_materials", 0.0)
        self.title.setText(f"👋 Привет, {full_name}!\n🧾 Ты уже сдал: {quantity} г сырья\n📦 Теперь отсканируй штрихкод бутылки")
        self.qr_label.hide()
        self.barcode_input.show()
        self.confirm_btn.show()
        self.confirm_btn.setEnabled(True)
        self.barcode_input.setFocus()

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
            r = requests.get(f"{API_BASE_URL}/recyclable-materials/by/barcode/{barcode}/")
            if r.status_code != 200:
                raise ValueError("Материал не найден")

            data = r.json()
            name, mtype, weight = data["name"], data["type"], data["weight"]
            self.info_label.setText(f"Материал: {name}\nТип: {mtype}\nВес: {weight} г")
            self.info_label.setStyleSheet("color: white;")
            self.info_label.show()

            if mtype == "plastic" and not self.cap_received:
                self.cap_required = True
                self.title.setText("🧢 Сначала сдайте крышку")
                self.barcode_input.clear()
                return

            self.ws_worker.send_material(barcode)
            self.material_sent.emit(name)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def on_material_sent(self, name):
        self.info_label.setStyleSheet("color: #00E676; font-weight: bold")
        self.info_label.setText(f"✅ {name} успешно отправлен!")
        self.barcode_input.clear()
        self.title.setText("📦 Сканируйте следующий штрихкод")