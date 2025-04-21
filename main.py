import sys
from PyQt5.QtWidgets import QApplication
from ui.home import HomeScreen

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HomeScreen()
    window.show()
    sys.exit(app.exec_())
