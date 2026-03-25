"""
Dock widget definitions
"""

from functools import partial
from typing import ClassVar, cast

from pydm.display import ScreenTarget, load_file
from pydm.utilities import IconFont, find_file
from pydm.utilities.macro import parse_macro_string
from qtpy.QtCore import Qt
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
        self.tab_widget.currentChanged.connect(self.show_correct_tab_buttons)

        self.attach_button = QToolButton()
        self.attach_button.setIcon(ifont.icon("arrow-down"))  # type: ignore
        self.attach_button.clicked.connect(self.reattach_user_choice)
        self.attach_button.setEnabled(False)
        self.tab_widget.setCornerWidget(self.attach_button, Qt.Corner.TopRightCorner)
        tab_bar = self.tab_widget.tabBar()
        tab_bar.setMinimumHeight(20)
        self.attach_button.setMinimumHeight(20)

        self.vlayout = QVBoxLayout()
        self.vlayout.addWidget(self.tab_widget)
        self.setLayout(self.vlayout)

    def show_correct_tab_buttons(self, new_idx: int):
        tab_bar = self.tab_widget.tabBar()
        for idx in range(self.tab_widget.count()):
            button = tab_bar.tabButton(idx, tab_bar.ButtonPosition.RightSide)
            if button is None:
                continue
            if idx == new_idx:
                button.show()
            else:
                button.hide()

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

        button_row = QWidget()

        detach_button = QToolButton()
        detach_button.setIcon(ifont.icon("arrow-up"))  # type: ignore
        detach_button.clicked.connect(self.detach_from_dock)
        close_button = QToolButton()
        close_button.setIcon(ifont.icon("window-close"))  # type: ignore
        close_button.clicked.connect(self.close_tab)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(3, 0, 0, 0)
        hlayout.addWidget(detach_button)
        hlayout.addWidget(close_button)
        button_row.setLayout(hlayout)

        tab_bar = self.tab_widget.tabBar()
        tab_bar.setTabButton(idx, tab_bar.ButtonPosition.RightSide, button_row)
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
        self.update_attach_enabled()

    @classmethod
    def reattach_user_choice(cls):
        self = cls._instance
        self.clean_detached_widgets()
        if not self.detached_widgets:
            return
        elif len(self.detached_widgets) == 1:
            widget = self.detached_widgets[0]
            self.attach_to_dock(widget)
        else:
            self.show_attach_menu()

    @classmethod
    def attach_to_dock(cls, widget: QWidget):
        self = cls._instance
        self.add_to_dock(title=widget.windowTitle(), widget=widget, new_tab=True)
        if widget in self.detached_widgets:
            self.detached_widgets.remove(widget)
        self.clean_detached_widgets()

    def show_attach_menu(self) -> QMenu:
        self.clean_detached_widgets()
        menu = QMenu(self.attach_button)
        for widget in self.detached_widgets:
            action = menu.addAction(widget.windowTitle())
            action.triggered.connect(partial(self.attach_to_dock, widget))
        menu.popup(QCursor().pos())
        return menu

    def clean_detached_widgets(self):
        for display in list(self.detached_widgets):
            if not display.isVisible():
                self.detached_widgets.remove(display)
        self.update_attach_enabled()

    def update_attach_enabled(self):
        self.attach_button.setEnabled(bool(self.detached_widgets))

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
