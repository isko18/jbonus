import asyncio
from ws.worker import WebSocketWorker
from PyQt5.QtCore import QObject

class WebSocketManager(QObject):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.task = None

    def start_worker(self, loop):
        if self.worker:  # Если уже есть активный воркер, сначала остановить
            self.stop_worker(loop)

        self.worker = WebSocketWorker()
        self.task = asyncio.run_coroutine_threadsafe(self.worker.start(), loop)
        return self.worker

    def stop_worker(self, loop):
        if self.worker:
            close_future = asyncio.run_coroutine_threadsafe(self.worker.close(), loop)
            try:
                close_future.result(timeout=5)  # Подождать завершение корректного закрытия
            except Exception as e:
                print(f"⚠️ Ошибка при остановке WebSocketWorker: {e}")
            self.worker = None
            self.task = None
