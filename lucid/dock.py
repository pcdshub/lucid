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
        self.tab_widget.setMovable(True)
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
    def add_to_dock(cls, title: str, widget: QWidget, new_tab: bool = False):
        if not cls._instance.isVisible():
            return cls.open_in_new_window(title=title, widget=widget)
        if new_tab:
            print(f"Placeholder: would add {title}, {widget} to dock in a new tab")
        else:
            print(f"Placeholder: would add {title}, {widget} to dock, overriding the current tab")

    @classmethod
    def detach_from_dock(cls):
        print("Placeholder: would detach current tab from dock")

    @classmethod
    def open_in_new_window(cls, title: str, widget: QWidget):
        print(f"Placeholder: would open {title}, {widget} in new window")
