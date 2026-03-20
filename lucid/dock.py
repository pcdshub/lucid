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

        self.detached_widgets: list[QWidget] = []

        self.tab_widget = QTabWidget()
        self.tab_widget.setMovable(True)
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.attach_button = QPushButton()
        self.attach_button.setText("Attach to dock")
        self.attach_button.clicked.connect(self.reattach_to_dock)

        self.detach_button = QPushButton()
        self.detach_button.setText("Detach from dock")
        self.detach_button.clicked.connect(self.detach_from_dock)

        self.grid_layout = QGridLayout()
        self.grid_layout.addWidget(self.tab_widget, 0, 0, 1, 4)
        self.grid_layout.addWidget(self.attach_button, 1, 2)
        self.grid_layout.addWidget(self.detach_button, 1, 3)
        self.setLayout(self.grid_layout)

    @classmethod
    def add_to_dock(cls, title: str, widget: QWidget, new_tab: bool = False):
        if not cls._instance.isVisible():
            return cls.open_in_new_window(title=title, widget=widget)
        self = cls._instance
        if not new_tab and self.tab_widget.count() > 0:
            self.tab_widget.removeTab(self.tab_widget.currentIndex())
        idx = self.tab_widget.addTab(widget, title)
        self.tab_widget.setCurrentIndex(idx)

    @classmethod
    def detach_from_dock(cls):
        self = cls._instance
        if self.tab_widget.count() <= 0:
            return
        widget = self.tab_widget.currentWidget()
        self.open_in_new_window(self.tab_widget.tabText(self.tab_widget.currentIndex()), widget)

    @classmethod
    def open_in_new_window(cls, title: str, widget: QWidget):
        self = cls._instance
        self.clean_detached_widgets()
        self.detached_widgets.append(widget)
        widget.setParent(None)  # type: ignore
        widget.setWindowTitle(title)
        widget.show()

    @classmethod
    def reattach_to_dock(cls, widget: QWidget | None = None):
        self = cls._instance
        self.clean_detached_widgets()
        if not self.detached_widgets:
            return
        # Some slots send things like ints or bools into the arg
        if not isinstance(widget, QWidget):
            if len(self.detached_widgets) == 1:
                widget = self.detached_widgets[0]
            else:
                our_pos = self.mapToGlobal(self.pos())
                widget = self.detached_widgets[0]
                nearest_sqdist = 1000000000000000
                for dwig in self.detached_widgets:
                    dpos = dwig.mapToGlobal(dwig.pos())
                    sqdist = (our_pos.x() - dpos.x()) ** 2 + (our_pos.y() - dpos.y()) ** 2
                    if sqdist < nearest_sqdist:
                        nearest_sqdist = sqdist
                        widget = dwig
        self.add_to_dock(title=widget.windowTitle(), widget=widget, new_tab=True)
        if widget in self.detached_widgets:
            self.detached_widgets.remove(widget)

    def clean_detached_widgets(self):
        for display in list(self.detached_widgets):
            if not display.isVisible():
                self.detached_widgets.remove(display)
