"""
Dock widget definitions
"""

from typing import ClassVar

from qtpy.QtWidgets import QGridLayout, QPushButton, QSizePolicy, QTabWidget, QWidget


class LucidDock(QWidget):
    _instance: ClassVar["LucidDock"]

    def __init__(self, parent: QWidget | None = None):
        LucidDock._instance = self
        super().__init__(parent)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setTabBarAutoHide(True)
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.attach_button = QPushButton()
        self.attach_button.setText("Attach to dock")

        self.detach_button = QPushButton()
        self.detach_button.setText("Detach from dock")

        self.grid_layout = QGridLayout()
        self.grid_layout.addWidget(self.tab_widget, 0, 0, 4, 0)
        self.grid_layout.addWidget(self.attach_button, 1, 3)
        self.grid_layout.addWidget(self.detach_button, 1, 4)
        self.setLayout(self.grid_layout)

    @classmethod
    def get_instance(cls) -> "LucidDock":
        return cls._instance

    def add_to_dock(self, title: str, widget: QWidget, new_tab: bool = False):
        print(f"Placeholder: would add {title}, {widget} to dock")

    def detach_from_dock(self):
        print("Placeholder: would detach from dock")
