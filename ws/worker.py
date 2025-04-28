from PyQt5.QtCore import QObject, pyqtSignal
import requests
import threading
import websocket
import json
import serial
import time
from utils.logger import get_logger



API_BASE_URL = "https://back.jashyl-bonus.kg/api/v1"

class WebSocketWorker(QObject):
    connected = pyqtSignal(dict)
    closed = pyqtSignal(int, str)
    error = pyqtSignal(str)
    cap_accepted_signal = pyqtSignal()
    session_ended = pyqtSignal()
    connected_state_changed = pyqtSignal(bool)
    socket_opened = pyqtSignal()  # Добавь рядом с другими сигналами


    def __init__(self):
        super().__init__()
        self.ws = None
        self.logger = get_logger()
        self.allowed_types = set()
        self.arduino = None
        self.is_connected = False
        self.cap_already_accepted = False
        self.running = False
        
        
        

        self.fandomat_id = "fan_bc539aed70f65db5544c5f38ec1a076250150a7802f341d9fa94729a32bc9c5c"
        self.fandomat_token = "fan_1c61b10c563dea103b0b4a0e74209d1cca9924c274fcaf1f17e39dcfeb545b23"
        self.fandomat_url = f"wss://back.jashyl-bonus.kg/ws/fandomat/{self.fandomat_id}/?token={self.fandomat_token}"

        self.load_supported_material_types()
        # self.setup_arduino()
        

    # def setup_arduino(self):
    #     try:
    #         self.arduino = serial.Serial(port='COM10', baudrate=9600, timeout=1)
    #         self.logger.info("✅ Arduino подключен на COM10")
    #         threading.Thread(target=self.listen_for_cap_signal, daemon=True).start()
    #     except Exception as e:
    #         self.logger.warning(f"⚠️ Не удалось подключить Arduino: {e}")

    # def listen_for_cap_signal(self):
    #     while self.arduino:
    #         try:
    #             if self.arduino.in_waiting:
    #                 line = self.arduino.readline().decode().strip()
    #                 self.logger.info(f"📥 Arduino: {line}")
    #                 if line == "CAP_OK" and not self.cap_already_accepted:
    #                     self.cap_already_accepted = True
    #                     self.logger.info("🧢 Крышка принята")
    #                     self.cap_accepted_signal.emit()
    #         except Exception as e:
    #             self.logger.error(f"❌ Ошибка чтения с Arduino: {e}")

    def load_supported_material_types(self):
        try:
            resp = requests.get(f"{API_BASE_URL}/recyclable-materials/types/")
            if resp.status_code == 200:
                self.allowed_types = set(resp.json())
            else:
                self.allowed_types = {"plastic", "iron", "aluminum", "food"}
            self.logger.info(f"✅ Допустимые типы: {self.allowed_types}")
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка загрузки типов: {e}")
            self.allowed_types = {"plastic", "iron", "aluminum", "food"}

    def start(self):
        print("✅ WebSocketWorker: старт в потоке")
        self.running = True

        def on_open(ws):
            self.is_connected = True
            self.logger.info("🟢 Fan WebSocket открыт. Ждём клиента...")
            self.connected_state_changed.emit(True)
            self.socket_opened.emit()  # 🔥 новый сигнал


        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("action") == "connect":
                    user = data.get("user_id")
                    if user:
                        self.logger.info(f"✅ Клиент подключился: {user}")
                        self.connected.emit(user)
                        threading.Timer(2, self.send_get_material).start()
                    else:
                        self.logger.warning("⚠️ Не удалось получить user_id")
                elif data.get("action") == "get_material":
                    self.logger.info(f"📦 get_material: {data}")
                elif data.get("action") == "set_material":
                    self.logger.info(f"✅ set_material: {data}")
                    self.cap_already_accepted = False
                elif data.get("action") == "disconnect":
                    self.cap_already_accepted = False
                    self.logger.info("🔴 Клиент завершил сессию")
                    self.session_ended.emit()
                    ws.close()
                elif data.get("error") and data["error"] != "Dont has any materials":
                    self.logger.error(f"❌ Ошибка сервера: {data['error']}")
            except Exception as e:
                self.logger.error(f"❗ Ошибка парсинга: {e}")
                self.error.emit(str(e))

        def on_error(ws, error):
            self.logger.error(f"❌ WebSocket ошибка: {error}")
            self.error.emit(str(error))
            self.connected_state_changed.emit(False)

        def on_close(ws, code, msg):
            self.logger.warning(f"🔒 WebSocket закрыт: {code}, {msg}")
            self.closed.emit(code, msg)
            self.is_connected = False
            self.connected_state_changed.emit(False)
            self.ws = None

        def run_ws_loop():
            while self.running:
                try:
                    self.ws = websocket.WebSocketApp(
                        self.fandomat_url,
                        on_open=on_open,
                        on_message=on_message,
                        on_error=on_error,
                        on_close=on_close
                    )
                    self.logger.info("🔄 Подключение к WebSocket...")
                    self.ws.run_forever(ping_interval=20, ping_timeout=10)
                except Exception as e:
                    self.logger.error(f"🛑 WebSocket авария: {e}")
                time.sleep(5)

        # 🧠 Запускаем цикл в отдельном потоке, чтобы GUI не зависал
        threading.Thread(target=run_ws_loop, daemon=True).start()


    def stop(self):
        self.logger.info("🛑 Остановка WebSocketWorker")
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                self.logger.warning(f"⚠️ Ошибка закрытия WebSocket: {e}")
        self.ws = None
        
    def send_material(self, barcode):
        try:
            resp = requests.get(f"{API_BASE_URL}/recyclable-materials/by/barcode/{barcode}/")
            if resp.status_code != 200:
                self.logger.warning(f"❌ Штрихкод {barcode} не найден")
                return
            data = resp.json()
            material_type = data.get("type")
            if material_type not in self.allowed_types:
                self.logger.warning(f"🚫 Тип '{material_type}' не поддерживается")
                return
        except Exception as e:
            self.logger.error(f"⚠️ Ошибка запроса штрихкода: {e}")
            return

        payload = {
            "action": "set_material",
            "material_type": barcode
        }

        if self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                self.logger.info(f"📤 Отправка: {payload}")
                self.ws.send(json.dumps(payload))
            except Exception as e:
                self.logger.error(f"❌ Ошибка отправки материала: {e}")
        else:
            self.logger.warning("⚠️ WebSocket неактивен — отправка невозможна")

    def send_get_material(self):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                self.ws.send(json.dumps({"action": "get_material"}))
                self.logger.info("🔍 Отправлен get_material")
            except Exception as e:
                self.logger.error(f"❌ Не удалось отправить get_material: {e}")
                
                

    def close(self):
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                self.logger.warning(f"⚠️ Ошибка закрытия WebSocket: {e}")
            self.ws = None
