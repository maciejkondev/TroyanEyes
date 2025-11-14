from PySide6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, 
    QHBoxLayout, QStackedWidget
)
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("KoniuBot")
        self.resize(600, 300)

        # --- ROOT LAYOUT -------------------------------------------------

        container = QWidget()
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- SIDEBAR -----------------------------------------------------

        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Navigation buttons
        self.btn_main = self.create_nav_btn("Main")
        self.btn_combat = self.create_nav_btn("Combat")
        self.btn_exp = self.create_nav_btn("EXP Farmer")
        self.btn_movement = self.create_nav_btn("Movement")
        self.btn_settings = self.create_nav_btn("Settings")

        # Add navigation buttons
        sidebar_layout.addWidget(self.btn_main)
        sidebar_layout.addWidget(self.btn_combat)
        sidebar_layout.addWidget(self.btn_exp)
        sidebar_layout.addWidget(self.btn_movement)
        sidebar_layout.addWidget(self.btn_settings)
        sidebar_layout.addStretch()

        # --- PAGE STACK --------------------------------------------------

        self.stack = QStackedWidget()
        self.stack.setObjectName("Content")

        # PAGE PLACEHOLDERS — you will add these later
        # -------------------------------------------------
        # from gui.pages.main_page import MainPage
        # from gui.pages.combat_page import CombatPage
        # from gui.pages.exp_page import ExpPage
        # from gui.pages.movement_page import MovementPage
        # from gui.pages.settings_page import SettingsPage
        #
        # self.page_main = MainPage()
        # self.page_combat = CombatPage()
        # self.page_exp = ExpPage()
        # self.page_movement = MovementPage()
        # self.page_settings = SettingsPage()
        #
        # self.stack.addWidget(self.page_main)
        # self.stack.addWidget(self.page_combat)
        # self.stack.addWidget(self.page_exp)
        # self.stack.addWidget(self.page_movement)
        # self.stack.addWidget(self.page_settings)
        # -------------------------------------------------

        # TEMPORARY PLACEHOLDERS so the app runs NOW
        # Remove these once you add real pages
        for name in ["Main Page", "Combat Page", "EXP Farmer Page", "Movement Page", "Settings Page"]:
            w = QWidget()
            w.setObjectName(name)
            self.stack.addWidget(w)

        # --- COMBINE SIDEBAR + STACK -------------------------------------

        main_layout.addWidget(self.sidebar, 1)
        main_layout.addWidget(self.stack, 5)

        self.setCentralWidget(container)

        # --- NAVIGATION SIGNALS ------------------------------------------

        self.btn_main.clicked.connect(lambda: self.switch_page(0))
        self.btn_combat.clicked.connect(lambda: self.switch_page(1))
        self.btn_exp.clicked.connect(lambda: self.switch_page(2))
        self.btn_movement.clicked.connect(lambda: self.switch_page(3))
        self.btn_settings.clicked.connect(lambda: self.switch_page(4))

        # Default selected
        self.btn_main.setChecked(True)

        # OPTIONAL: load QSS theme
        # self.apply_dark_theme()

    # ====================================================================
    # Helpers
    # ====================================================================

    def switch_page(self, index):
        """Switch displayed page"""
        self.stack.setCurrentIndex(index)
        self.uncheck_all()
        # mark selected button
        btn = [
            self.btn_main,
            self.btn_combat,
            self.btn_exp,
            self.btn_movement,
            self.btn_settings
        ][index]
        btn.setChecked(True)

    def uncheck_all(self):
        """Unselect all sidebar buttons"""
        for btn in [
            self.btn_main,
            self.btn_combat,
            self.btn_exp,
            self.btn_movement,
            self.btn_settings
        ]:
            btn.setChecked(False)

    def create_nav_btn(self, text):
        """Factory: modern sidebar button"""
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(40)
        btn.setStyleSheet("text-align: left; padding-left: 12px;")
        return btn

    def apply_dark_theme(self):
        """Load external QSS theme"""
        try:
            with open("assets/qss/dark.qss", "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("dark.qss not found → running without theme")
