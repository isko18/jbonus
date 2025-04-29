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
        self.websocket = None
        self.session = None

        self.fandomat_id = "fan_bc539aed70f65db5544c5f38ec1a076250150a7802f341d9fa94729a32bc9c5c"
        self.fandomat_token = "fan_1c61b10c563dea103b0b4a0e74209d1cca9924c274fcaf1f17e39dcfeb545b23"
        self.url = f"wss://back.jashyl-bonus.kg/ws/fandomat/{self.fandomat_id}/?token={self.fandomat_token}"

    async def load_supported_material_types(self):
        try:
            async with self.session.get(f"{API_BASE_URL}/recyclable-materials/types/") as resp:
                if resp.status == 200:
                    types = await resp.json()
                    self.allowed_types = set(types)
                else:
                    self.allowed_types = {"plastic", "iron", "aluminum", "food"}
            self.logger.info(f"✅ Допустимые типы: {self.allowed_types}")
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка загрузки типов: {e}")
            self.allowed_types = {"plastic", "iron", "aluminum", "food"}


    async def start(self):
        self.session = aiohttp.ClientSession()
        await self.load_supported_material_types()
        self.running = True
        reconnect_delay = 5

        while self.running:
            try:
                self.logger.info(f"🔄 Подключение к {self.url}")
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20, open_timeout=20) as websocket:
                    self.websocket = websocket
                    self.connected_state_changed.emit(True)
                    self.socket_opened.emit()
                    self.logger.info("🟢 WebSocket соединение открыто")

                    # ✨ Отправляем приветственное сообщение после подключения
                    await websocket.send(json.dumps({"action": "connect"}))
                    self.logger.info("👋 Отправлено начальное сообщение {action: connect}")

                    reconnect_delay = 5  # Сброс задержки после успешного подключения

                    async for message in websocket:
                        await self.handle_message(message)

            except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e:
                self.logger.warning(f"🔒 Соединение закрыто: {e.code} / {e.reason}")
                self.closed.emit(e.code, e.reason)
                self.connected_state_changed.emit(False)

            except asyncio.TimeoutError:
                self.logger.error("⏳ Таймаут при открытии WebSocket соединения")
                self.error.emit("Таймаут WebSocket соединения")
                self.connected_state_changed.emit(False)

            except Exception as e:
                self.logger.error(f"❌ Ошибка WebSocket: {str(e)}")
                self.error.emit(str(e))
                self.connected_state_changed.emit(False)

            if self.running:
                self.logger.info(f"⏳ Переподключение через {reconnect_delay} секунд...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)  # увеличиваем задержку, но максимум до 60 сек

    async def handle_message(self, message):
        try:
            data = json.loads(message)
            if data.get("action") == "connect":
                user = data.get("user_id")
                if user:
                    self.connected.emit(user)
                    self.logger.info(f"✅ Клиент подключился: {user}")
                    await asyncio.sleep(2)
                    await self.send_get_material()
            elif data.get("action") == "get_material":
                self.logger.info(f"📦 Получено get_material: {data}")
            elif data.get("action") == "set_material":
                self.logger.info(f"📤 Подтверждено set_material: {data}")
            elif data.get("action") == "disconnect":
                self.logger.info("🔴 Клиент завершил сессию")
                self.session_ended.emit()
                await self.close()
            elif data.get("error") and data["error"] != "Dont has any materials":
                self.logger.error(f"🚨 Сервер вернул ошибку: {data['error']}")
                self.error.emit(data["error"])
        except Exception as e:
            self.logger.error(f"❗ Ошибка парсинга сообщения: {e}")
            self.error.emit(str(e))

    async def fetch_material_info(self, barcode):
        try:
            async with self.session.get(f"{API_BASE_URL}/recyclable-materials/by/barcode/{barcode}/", timeout=5) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            self.logger.error(f"❌ Ошибка запроса материала: {e}")
            return None
    async def send_material(self, barcode):
        if not isinstance(self.websocket, WebSocketClientProtocol) or self.websocket.closed:
            self.logger.warning("⚠️ WebSocket неактивен — отправка невозможна")
            return

        data = await self.fetch_material_info(barcode)
        if not data:
            return

        material_type = data.get("type")
        if material_type not in self.allowed_types:
            self.logger.warning(f"🚫 Тип материала '{material_type}' не поддерживается")
            return

        payload = {
            "action": "set_material",
            "material_type": barcode
        }

        try:
            await self.websocket.send(json.dumps(payload))
            self.logger.info(f"📤 Отправка материала: {payload}")
            await asyncio.sleep(1)
            await self.send_get_material()
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки через WebSocket: {e}")
            self.error.emit(str(e))

    async def send_get_material(self):
        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.send(json.dumps({"action": "get_material"}))
                self.logger.info("🔍 Отправлен запрос get_material")
            except Exception as e:
                self.logger.error(f"❌ Ошибка отправки get_material: {e}")
                self.error.emit(str(e))

    async def close(self):
        self.running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        if self.session:
            await self.session.close()  # закрыть сессию
            self.session = None

