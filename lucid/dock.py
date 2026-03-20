"""
Dock widget definitions
"""

from typing import ClassVar, cast

from pydm.display import ScreenTarget, load_file
from pydm.utilities import IconFont, find_file
from pydm.utilities.macro import parse_macro_string
from qtpy.QtCore import Qt
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QApplication, QGridLayout, QPushButton, QSizePolicy, QTabWidget, QWidget

try:
    from qtpy.QtCore import Property  # type: ignore
except ImportError:
    from qtpy.QtCore import pyqtProperty as Property  # type: ignore

ifont = IconFont()


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

        self.close_button = QPushButton()
        self.close_button.setText("Close Tab")
        self.close_button.clicked.connect(self.close_tab)

        self.grid_layout = QGridLayout()
        self.grid_layout.addWidget(self.tab_widget, 0, 0, 1, 6)
        self.grid_layout.addWidget(self.attach_button, 1, 3)
        self.grid_layout.addWidget(self.detach_button, 1, 4)
        self.grid_layout.addWidget(self.close_button, 1, 5)
        self.setLayout(self.grid_layout)

    @classmethod
    def add_to_dock(cls, title: str, widget: QWidget, new_tab: bool = False):
        if not cls._instance.isVisible():
            return cls.open_in_new_window(title=title, widget=widget)
        self = cls._instance
        idx = None
        if not new_tab and self.tab_widget.count() > 0:
            idx = self.tab_widget.currentIndex()
            self.tab_widget.removeTab(idx)
        if idx is None:
            idx = self.tab_widget.addTab(widget, title)
        else:
            self.tab_widget.insertTab(idx, widget, title)
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

    def close_tab(self):
        self.tab_widget.removeTab(self.tab_widget.currentIndex())


class LucidDockButton(QPushButton):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._filename: str = ""
        self._macro: str = ""
        self.clicked.connect(self.open_in_dock)
        self._icon = ifont.icon("anchor")
        self.setCursor(QCursor(self._icon.pixmap(16, 16)))  # type: ignore

    def open_in_dock(self):
        fname = find_file(
            self._filename,
            raise_if_not_found=True,
        )
        macros = parse_macro_string(self._macro)

        display = cast(QWidget, load_file(fname, macros=macros, target=ScreenTarget.DIALOG))

        detached = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
        if detached:
            LucidDock.open_in_new_window(title=display.windowTitle(), widget=display)
        else:
            new_tab = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
            LucidDock.add_to_dock(title=display.windowTitle(), widget=display, new_tab=new_tab)

    def readFilename(self) -> str:
        return self._filename

    def setFilename(self, val: str) -> None:
        self._filename = val

    filename = Property("QString", readFilename, setFilename)

    def readMacro(self) -> str:
        return self._macro

    def setMacro(self, new_macro: str) -> None:
        self._macro = new_macro

    macros = Property("QString", readMacro, setMacro)
