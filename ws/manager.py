import asyncio
from ws.worker import WebSocketWorker
from PyQt5.QtCore import QObject

class WebSocketManager(QObject):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.task = None

    def start_worker(self, loop):
        self.worker = WebSocketWorker()
        self.task = asyncio.run_coroutine_threadsafe(self.worker.start(), loop)
        return self.worker

    def stop_worker(self, loop):
        if self.worker:
            asyncio.run_coroutine_threadsafe(self.worker.close(), loop)
            self.worker = None
            self.task = None
