from PyQt5.QtCore import QObject, pyqtSignal
import threading
import serial
import serial.tools.list_ports
from utils.logger import get_logger

class ArduinoManager(QObject):
    cap_accepted = pyqtSignal()
    bottle_accepted = pyqtSignal()
    aluminum_verified = pyqtSignal()

    def __init__(self, ports_to_use=None):
        super().__init__()
        self.logger = get_logger()
        self.ports_to_use = ports_to_use
        self.arduinos = []
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        self.running = True
        try:
            all_ports = serial.tools.list_ports.comports()
            ports = [p for p in all_ports if p.device in self.ports_to_use] if self.ports_to_use else all_ports

            if not ports:
                self.logger.warning("❗ Нет доступных портов для подключения Arduino.")
                return

            for port in ports:
                try:
                    arduino = serial.Serial(port.device, baudrate=9600, timeout=1)
                    self.arduinos.append(arduino)
                    self.logger.info(f"✅ Arduino подключен: {port.device}")
                    threading.Thread(target=self.listen_to_arduino, args=(arduino,), daemon=True).start()
                except Exception as e:
                    self.logger.warning(f"⚠️ Не удалось подключить {port.device}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Ошибка сканирования портов: {e}")

    def listen_to_arduino(self, arduino):
        while self.running:
            try:
                if arduino.in_waiting:
                    with self.lock:
                        line = arduino.readline().decode(errors="ignore").strip()
                    if line:
                        self.handle_message(line)
            except Exception as e:
                self.logger.error(f"❌ Ошибка чтения с {arduino.port}: {e}")
                try:
                    self.arduinos.remove(arduino)
                    self.logger.warning(f"⚠️ Arduino {arduino.port} удалён из списка.")
                except ValueError:
                    pass
                break

    def handle_message(self, message):
        self.logger.info(f"📥 Сообщение от Arduino: {message}")

        if message == "cap_accepted":
            self.logger.info("🧢 Крышка принята!")
            self.cap_accepted.emit()
        elif message == "bottle_accepted":
            self.logger.info("🍾 Бутылка принята!")
            self.bottle_accepted.emit()
        elif message == "BOT_OK3":
            self.logger.info("✅ BOT_OK3 получен — алюминий подтверждён!")
            self.aluminum_verified.emit()
        elif any(kw in message for kw in ["жду команду", "система готова", "close завершён"]):
            self.logger.info(f"ℹ️ Статус: {message}")
        else:
            self.logger.warning(f"⚠️ Неизвестное сообщение: {message}")

    def send_to_all(self, text):
        for arduino in list(self.arduinos):
            try:
                if arduino.is_open:
                    with self.lock:
                        arduino.write((text + "\n").encode())
                    self.logger.info(f"📤 Отправлено: {text}")
                else:
                    self.logger.warning(f"⚠️ Порт {arduino.port} закрыт, сообщение не отправлено.")
            except Exception as e:
                self.logger.error(f"❌ Ошибка отправки на {arduino.port}: {e}")

    def stop(self):
        self.running = False
        for arduino in list(self.arduinos):
            try:
                if arduino.is_open:
                    arduino.close()
                    self.logger.info(f"🔒 Порт {arduino.port} закрыт")
            except Exception as e:
                self.logger.error(f"⚠️ Ошибка при закрытии порта {arduino.port}: {e}")
        self.arduinos.clear()
