import threading
from .worker import WebSocketWorker

class WebSocketManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.worker = None
            cls._instance.thread = None
        return cls._instance

    def start_worker(self):
        self.stop()

        self.worker = WebSocketWorker()
        self.thread = threading.Thread(target=self.worker.start, daemon=True)
        self.thread.start()

        return self.worker

    def stop(self):
        if self.worker:
            try:
                self.worker.stop()  # 🛑 теперь есть метод stop
            except Exception as e:
                print(f"❌ Ошибка при остановке WebSocketWorker: {e}")
            self.worker = None

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)  # ⏳ дождёмся завершения
        self.thread = None

