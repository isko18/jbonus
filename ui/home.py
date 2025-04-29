from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QGraphicsOpacityEffect, QMessageBox, QHBoxLayout
)
from PyQt5.QtGui import QPixmap, QFont, QIcon, QMovie, QColor, QFontDatabase
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
import os
import requests
from utils.qr_generator import generate_qr
from utils.image_loader import load_image_from_file
from ws.manager import WebSocketManager
from PyQt5.QtSvg import QSvgWidget
from ws.arduino_manager import ArduinoManager
import asyncio
import time
from PyQt5.QtCore import QThread

FANDOMAT_TOKEN = "fan_bc539aed70f65db5544c5f38ec1a076250150a7802f341d9fa94729a32bc9c5c"
API_BASE_URL = "https://back.jashyl-bonus.kg/api/v1"

class HomeScreen(QWidget):
    material_sent = pyqtSignal(str)
    info_text_requested = pyqtSignal(str) 

    def __init__(self, loop, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Фандомат")
        self.setMinimumSize(380, 500)
        self.resize(600, 900)
        self.setWindowIcon(QIcon("assets/icons/image.png"))

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
        self.scanned_code = ""
        self.pending_barcode_for_send = None


        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)
        self.loop = loop 
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
        self.current_barcode = None
        self.waiting_for_bottle = False

        self.arduino_manager = ArduinoManager(ports_to_use=["COM11", "COM9"])
        self.arduino_manager.cap_accepted.connect(self.on_cap_received)
        self.arduino_manager.bottle_accepted.connect(self.on_bottle_received)
        # self.arduino_manager.aluminum_accepted.connect(self.on_aluminum_received)
        self.arduino_manager.aluminum_verified.connect(lambda: asyncio.run_coroutine_threadsafe(self.on_aluminum_verified(), self.loop))

        self.waiting_label = QLabel(alignment=Qt.AlignCenter)



        self.arduino_manager.start()
        

        # ------------------- HEADER -------------------
        header_widget = QWidget()
        header_widget.setFixedHeight(160)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(30, 30, 30, 30)
        header_layout.setSpacing(20)

        # Logo


        # SVG Logo
        logo = QSvgWidget(os.path.join("assets", "icons", "Group 7 (1).svg"))  # путь к svg-файлу
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
# Контейнер для баннера
        banner_container = QWidget()
        banner_layout = QVBoxLayout(banner_container)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        banner_layout.setSpacing(0)
        banner_layout.setAlignment(Qt.AlignCenter)  # Центрируем всё внутри!

        self.ad_label = QLabel(alignment=Qt.AlignCenter)
        self.ad_label.setMinimumSize(900, 900)  # Можно регулировать минимальный размер баннера
        self.ad_label.setScaledContents(True)   # Растягивание в пределах контейнера при необходимости

        banner_layout.addWidget(self.ad_label)
        
        # внутри banner_layout:
        self.svg_widget = QSvgWidget()
        self.svg_widget.setFixedSize(1200, 720)
        self.svg_widget.setVisible(False)  # Пока скрыт
        banner_layout.addWidget(self.svg_widget, alignment=Qt.AlignCenter)


        self.waiting_label.setScaledContents(True)
        self.waiting_label.hide()

        banner_layout.addWidget(self.waiting_label)

        self.status_indicator = QLabel("", alignment=Qt.AlignCenter)
        self.status_indicator.setVisible(False)
        self.status_gif = QMovie("assets/icons/loading.gif")
        self.status_indicator.setMovie(self.status_gif)
        self.layout.addWidget(self.status_indicator)

        self.qr_label = QLabel(alignment=Qt.AlignCenter)
        self.qr_label.hide()
        banner_layout.addWidget(self.qr_label)

        self.qr_hint_label = QLabel(
            "Отсканируйте QR-код своим приложением для начала сдачи сырья",
            alignment=Qt.AlignCenter
        )
        self.qr_hint_label.setFont(QFont("Nunito", 14, QFont.Bold))
        self.qr_hint_label.setStyleSheet("color:#212121; margin-top: 10px;")
        self.qr_hint_label.setWordWrap(True)
        self.qr_hint_label.hide()
        banner_layout.addWidget(self.qr_hint_label)  # ✅ вот это добавление решает проблему


        self.layout.addWidget(banner_container, stretch=1)  # Растягиваем контейнер в общем лейауте

        self.info_label = QLabel(alignment=Qt.AlignCenter)
        self.info_label.hide()
        self.layout.addWidget(self.info_label)

        # ------------------- BUTTONS (Start / Back) -------------------
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 40)  # Отступ снизу побольше
        buttons_layout.setSpacing(10)
        buttons_layout.setAlignment(Qt.AlignBottom)  # Прижимаем кнопки вниз в контейнере

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


    def connect_signals(self):
        self.material_sent.connect(self.on_material_sent)
        self.info_text_requested.connect(self.show_info_animation) 

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.scanned_code:
                barcode = self.scanned_code.strip()
                self.scanned_code = ""
                if self.waiting_for_bottle:
                    self.process_bottle_scan(barcode)
                elif getattr(self, 'waiting_for_aluminum', False):
                    asyncio.run_coroutine_threadsafe(self.process_aluminum_scan(barcode), self.loop)
                else:
                    asyncio.run_coroutine_threadsafe(self.process_scanned_barcode(barcode), self.loop)
        else:
            text = event.text()
            if text.isdigit():
                self.scanned_code += text

                
    async def process_scanned_barcode(self, barcode):
        if not barcode:
            return
        try:
            r = await asyncio.to_thread(requests.get, f"{API_BASE_URL}/recyclable-materials/by/barcode/{barcode}/", timeout=5)
            r.raise_for_status()
            data = r.json()
            mtype = data.get("type", "")

            if mtype == "plastic":
                self.current_barcode = barcode
                self.waiting_for_cap = True  # <<< новый флаг ожидания крышки
                self.show_info_animation("Положите крышку")
                self.arduino_manager.send_to_all("on_cap")
            elif mtype == "iron":
                self.current_barcode = barcode
                self.show_info_animation("Положите алюминиевую банку")
                self.arduino_manager.send_to_all("open_ca")
                self.waiting_for_aluminum = True
            else:
                self.current_barcode = None
                await self.accept_material_directly(barcode)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))



    async def process_aluminum_scan(self, barcode):
        if barcode == self.current_barcode:
            self.show_info_animation("✅ Проверка алюминия...")
            self.pending_barcode_for_send = barcode  # <<< СЮДА СОХРАНЯЕМ ДЛЯ ОТПРАВКИ
            # await asyncio.sleep(2)
            await self.arduino_manager.send_to_all("PUSH")
            self.current_barcode = None  # <<< обнуляем текущий штрихкод после PUSH
            self.waiting_for_aluminum = False
        else:
            self.show_info_animation("⚠️ Алюминий не совпал")
            self.arduino_manager.send_to_all("push_front")
            self.current_barcode = None 



    async def accept_material_directly(self, barcode):
        self.show_info_animation("✅ Материал принят!")
        print(f"[DEBUG] Отправка материала: {barcode}")  # 👈 ЛОГ
        
        if self.ws_worker:
            print("[DEBUG] ws_worker существует, отправляем материал...")  # 👈 ЛОГ
            await self.ws_worker.send_material(barcode)
        else:
            print("[DEBUG] ws_worker = None")  # 👈 ЛОГ

        self.material_sent.emit(barcode)
        QTimer.singleShot(2000, self.reset_to_home)




    def update_time(self):
        from datetime import datetime
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M"))
        months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
                  "августа", "сентября", "октября", "ноября", "декабря"]
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
                pixmap.scaled(self.ad_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

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
        svg_path = os.path.join("assets", "icons", "5.svg")
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
        # self.status_gif.stop()
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
            # WebSocketManager().stop()
            self.ws_worker = None
            QTimer.singleShot(2000, self._start_ws)
        else:
            self._start_ws()

    def _start_ws(self):
        self.ws_worker = WebSocketManager().start_worker(self.loop)
        self.ws_worker.connected.connect(self.on_ws_connected)
        self.ws_worker.session_ended.connect(self.on_session_ended)
        self.ws_worker.error.connect(lambda msg: self.show_status(f"❌ WebSocket ошибка: {msg}"))
        self.ws_worker.connected_state_changed.connect(self.on_connection_state_changed)
        self.ws_worker.socket_opened.connect(self.on_socket_opened)
        self.show_loading_overlay()
        
    def on_ws_connected(self, user):
        self.hide_status()
        self.qr_label.hide()
        self.qr_hint_label.hide()
        self.start_btn.hide()
        self.back_btn.hide()
        self.info_label.hide()

        # Скрыть баннер
        self.ad_label.hide()
        self.waiting_label.hide()

        # Загрузить и показать SVG
        svg_path = "assets/icons/ШТРИХ-КОД.svg"
        if not os.path.exists(svg_path):
            print(f"Ошибка: SVG-файл {svg_path} не найден!")
            return

        self.svg_widget.load(svg_path)
        self.svg_widget.setVisible(True)

        print("✅ SVG успешно загружен и отображён в баннерной зоне")

        
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
        self.info_label.hide()
        self.ad_label.clear()  # <-- Очистить ad_label
        self.loaded_pixmap = None  # <-- Очистить ссылку на старый баннер
        self.ad_label.show()
        self.hide_status()
        self.cap_required = False
        self.cap_received = False
        self.session_active = False
        self.start_btn.show()
        self.back_btn.hide()
        self.waiting_label.hide()
        self.ws_worker = None

        # Перезапускаем таймер баннеров
        if hasattr(self, "banner_timer"):
            self.banner_timer.stop()

        if self.banner_urls:
            self.current_banner_index = 0
            self.show_banner(self.banner_urls[0])
            self.banner_timer.start(5000)  # <-- добавьте, если нужен повтор
        else:
            self.load_banners()



    async def on_aluminum_verified(self):
        self.waiting_for_aluminum = False
        self.show_info_animation("Алюминиевая банка принята ✅. Положите банку в отсек")

        if self.ws_worker and self.pending_barcode_for_send:
            await self.ws_worker.send_material(self.pending_barcode_for_send)
            self.pending_barcode_for_send = None
        else:
            print("[WARNING] Не отправлен set_material — либо ws_worker=None, либо barcode=None")

        QTimer.singleShot(2000, self.finish_session)


    def on_cap_received(self):
        if getattr(self, 'waiting_for_cap', False):
            self.show_info_animation("Крышка принята ✅. Теперь положите бутылку в отсек")
            self.arduino_manager.send_to_all("open_bottle")
            self.waiting_for_cap = False
            self.waiting_for_bottle = True
        else:
            self.show_info_animation("Крышка принята ✅")


    def process_bottle_scan(self, barcode):
        if barcode == self.current_barcode:
            self.show_info_animation("✅ Бутылка совпала")
            self.pending_barcode_for_send = barcode  # Сохраняем для отправки позже
            self.arduino_manager.send_to_all("go_bottle")
            self.current_barcode = None
        else:
            self.show_info_animation("⚠️ Бутылка не совпала")
            self.arduino_manager.send_to_all("push_back")
            self.current_barcode = None




    def on_bottle_received(self):
        self.show_info_animation("Бутылка принята ✅")

        if self.pending_barcode_for_send:
            barcode = self.pending_barcode_for_send
        else:
            barcode = self.current_barcode

        if barcode and self.ws_worker:
            asyncio.run_coroutine_threadsafe(self.ws_worker.send_material(barcode), self.loop)
        else:
            print("[WARNING] Не отправлен set_material — нет barcode или ws_worker")

        self.finish_session()

    def on_aluminum_received(self):
        self.show_info_animation("Алюминий принят ✅")
        self.finish_session()


    def show_info_animation(self, text):
        self.info_label.setText(text)
        self.info_label.setStyleSheet("color: #00E676; font-weight: bold; font-size: 24px;")
        self.info_label.show()
        
    def finish_session(self):
        self.waiting_for_bottle = False
        self.waiting_label.hide()  # <<< спрятать картинку ожидания после сдачи сырья
        barcode_text = self.current_barcode if self.current_barcode else "материал"
        self.current_barcode = None
        self.pending_barcode_for_send = None

        # self.show_info_animation(f"✅ {barcode_text} принят!")

        QTimer.singleShot(2000, self.prepare_for_next_material)

    def prepare_for_next_material(self):
        self.info_label.hide()
        self.waiting_label.show()  # снова показываем "ожидание" для следующего штрихкода
        self.show_info_animation("✅ Готово! Положите следующее сырьё или завершите сессию.")


    def on_material_sent(self, name):
            self.info_label.setStyleSheet("color: #00E676; font-weight: bold")
            self.info_label.setText(f"✅ {name} успешно отправлен!")

    def resizeEvent(self, event):
        if self.loaded_pixmap:
            self.ad_label.setPixmap(
                self.loaded_pixmap.scaled(
                    self.ad_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        return super().resizeEvent(event)
