import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PySide6.QtCore import QTimer

from db import init_db
from tabs.map_tab import MapTab
from tabs.packets_tab import PacketsTab
from tabs.system_tab import SystemTab
from config import APP_NAME


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(1000, 700)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.map_6h_tab = MapTab(mode="6h")
        self.map_30d_tab = MapTab(mode="30d")
        self.packets_tab = PacketsTab()
        self.system_tab = SystemTab()

        self.tabs.addTab(self.map_6h_tab, "Carte 6h")
        self.tabs.addTab(self.map_30d_tab, "Carte 30 jours")
        self.tabs.addTab(self.packets_tab, "Réception")
        self.tabs.addTab(self.system_tab, "Système / Envoi")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_tabs)
        self.timer.start(5000)

    def refresh_tabs(self):
        for tab in [self.map_6h_tab, self.map_30d_tab, self.packets_tab, self.system_tab]:
            if hasattr(tab, "refresh"):
                try:
                    tab.refresh()
                except Exception as e:
                    print(f"Erreur refresh {tab.__class__.__name__}: {e}")


if __name__ == "__main__":
    init_db()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
