import requests
from PyQt5.QtGui import QPixmap

def load_image_from_file(path):
    pixmap = QPixmap(path)
    return pixmap if not pixmap.isNull() else None