import asyncio
import json
import aiohttp
import websockets
from PyQt5.QtCore import QObject, pyqtSignal
from websockets.legacy.client import WebSocketClientProtocol
from utils.logger import get_logger

API_BASE_URL = "https://back.jashyl-bonus.kg/api/v1"

class WebSocketWorker(QObject):
    connected = pyqtSignal(dict)
    closed = pyqtSignal(int, str)
    error = pyqtSignal(str)
    session_ended = pyqtSignal()
    connected_state_changed = pyqtSignal(bool)
    socket_opened = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.allowed_types = {"plastic", "iron", "aluminum", "food"}
        self.running = False
        self.websocket: WebSocketClientProtocol = None
        self.session: aiohttp.ClientSession = None

        self.fandomat_id = "fan_bc539aed70f65db5544c5f38ec1a076250150a7802f341d9fa94729a32bc9c5c"
        self.fandomat_token = "fan_1c61b10c563dea103b0b4a0e74209d1cca9924c274fcaf1f17e39dcfeb545b23"
        self.url = f"wss://back.jashyl-bonus.kg/ws/fandomat/{self.fandomat_id}/?token={self.fandomat_token}"

    async def load_supported_material_types(self):
        try:
            async with self.session.get(f"{API_BASE_URL}/recyclable-materials/types/") as resp:
                if resp.status == 200:
                    types = await resp.json()
                    self.allowed_types = set(types)
            self.logger.info(f"✅ Допустимые типы: {self.allowed_types}")
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка загрузки типов: {e}")

    async def start(self):
        self.session = aiohttp.ClientSession()
        await self.load_supported_material_types()
        self.running = True
        reconnect_delay = 5
        while self.running:
            try:
                self.logger.info(f"🔄 Подключение к {self.url}")
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20, open_timeout=25) as websocket:
                    self.websocket = websocket
                    self.connected_state_changed.emit(True)
                    self.socket_opened.emit()
                    self.logger.info("🟢 WebSocket соединение открыто")

                    reconnect_delay = 5

                    async for message in websocket:
                        await self.handle_message(message)

            except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e:
                self.logger.warning(f"🔒 Соединение закрыто: {e.code} / {e.reason}")
                self.closed.emit(e.code, e.reason)
                self.connected_state_changed.emit(False)
            except Exception as e:
                self.logger.exception(f"❌ Ошибка WebSocket: {e}")

            if self.running:
                self.logger.info(f"⏳ Переподключение через {reconnect_delay} сек...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

    async def handle_message(self, message):
        try:
            data = json.loads(message)
            action = data.get("action")

            if action == "connect":
                user = data.get("user_id")
                if user:
                    self.logger.info(f"✅ Клиент подключился: {user}")
                    self.connected.emit(user)
                    await self.send_get_material()

            elif action == "get_material":
                self.logger.info(f"📦 Получено get_material: {data}")

            elif action == "set_material":
                self.logger.info(f"📤 Подтверждено set_material: {data}")

            elif action == "disconnect":
                self.logger.info("🔴 Клиент завершил сессию")
                self.session_ended.emit()
                await self.close()

            elif "error" in data and data["error"] != "Dont has any materials":
                self.logger.error(f"🚨 Сервер вернул ошибку: {data['error']}")
                self.error.emit(data["error"])

            else:
                self.logger.warning(f"⚠️ Неожиданное сообщение: {data}")

        except json.JSONDecodeError as e:
            self.logger.error(f"❗ Ошибка JSON: {e}")
            self.error.emit("Ошибка разбора данных от сервера")
        except Exception as e:
            self.logger.error(f"❗ Ошибка обработки сообщения: {e}")
            self.error.emit(str(e))

    async def fetch_material_info(self, barcode):
        try:
            async with self.session.get(f"{API_BASE_URL}/recyclable-materials/by/barcode/{barcode}/", timeout=5) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    self.logger.warning(f"❌ Материал по штрихкоду {barcode} не найден")
                    return None
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения материала: {e}")
            return None

    async def send_material(self, barcode):
        print(f"[WS DEBUG] Отправка JSON: {{'action': 'set_material', 'material_type': {barcode}}}")
        print(f"[WS DEBUG] Отправка материала через WebSocket: {barcode}")
        if not self.websocket or (hasattr(self.websocket, "closed") and self.websocket.closed):
            self.logger.warning("⚠️ WebSocket не подключен или закрыт")
            return

        material_info = await self.fetch_material_info(barcode)
        if not material_info:
            return

        material_type = material_info.get("type")
        if material_type not in self.allowed_types:
            self.logger.warning(f"🚫 Тип '{material_type}' не поддерживается")
            return

        payload = {
            "action": "set_material",
            "material_type": barcode  # <=== ОТПРАВЛЯЕМ BARCODE
        }

        try:
            await self.websocket.send(json.dumps(payload))
            self.logger.info(f"📤 Отправка материала: {payload}")
            await asyncio.sleep(1)
            await self.send_get_material()
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки материала: {e}")
            self.error.emit(str(e))


    async def send_get_material(self):
        if not self.websocket or (hasattr(self.websocket, "closed") and self.websocket.closed):
            self.logger.warning("⚠️ WebSocket не подключен или закрыт")
            return
        try:
            await self.websocket.send(json.dumps({"action": "get_material"}))
            self.logger.info("🔍 Отправлен get_material")
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки get_material: {e}")
            self.error.emit(str(e))

    async def close(self):
        self.running = False
        if self.websocket:
            if hasattr(self.websocket, "close") and not self.websocket.closed:
                await self.websocket.close()
            self.websocket = None

        if self.session:
            if not self.session.closed:
                await self.session.close()
            self.session = None
