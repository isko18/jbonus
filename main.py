import sys
import asyncio
import threading
from PyQt5.QtWidgets import QApplication
from ui.home import HomeScreen

def start_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # СНАЧАЛА создаём loop
    asyncio_loop = asyncio.new_event_loop()
    threading.Thread(target=start_asyncio_loop, args=(asyncio_loop,), daemon=True).start()

    # Теперь передаём loop в HomeScreen
    window = HomeScreen(loop=asyncio_loop)
    window.show()

    sys.exit(app.exec())
