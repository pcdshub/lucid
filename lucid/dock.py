"""
Dock widget definitions
"""

from functools import partial
from typing import ClassVar, cast

from pydm.display import ScreenTarget, clear_compiled_ui_file_cache, load_file
from pydm.utilities import IconFont, find_file
from pydm.utilities.macro import parse_macro_string
from pydm.utilities.stylesheet import merge_widget_stylesheet
from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import (
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

from .utils import ctrl_pressed, shift_pressed

ifont = IconFont()


class LucidDock(QWidget):
    """
    The right-hand widget in the main screen that other screens can be embedded within.

    This is basically a tab widget that implements some dock/undock functionality.

    It is expected but not enforced that only one LucidDock exists at a time.
    Most of the functionality is exposed as classmethods so that other code does not have
    to locate the dock singleton, instead you can reference the LucidDock class directly.

    You should usually populate the dock by calling LucidDock.add_to_dock_user_choice,
    which will:
    - Replace the current tab if no modifiers are held
    - Add a new tab if the ctrl modifier key is held
    - Open in a new window if the shift modifier key is held
    - Open in a new window if the dock is not visible

    Parameters
    ----------
    parent : QWidget, optional
        Standard qt parent argument
    """

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
        """
        Ensure that the undock/close buttons are only visible on the active tab.

        Otherwise, it's really easy to accidentally close/undock tabs when trying to change tabs.

        Parameters
        ----------
        new_idx : int
            The integer of the currently open tab. This is intended be passed by the QTabWidget's
            "currentChanged" signal.
        """
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
    def add_to_dock_user_choice(cls, title: str, widget: QWidget):
        """
        The main way other code should add widgets to the dock.

        This checks the user's keypresses and opens the widget in the current tab (default),
        a new tab (ctrl), or a new window (shift, or invisible dock) as appropriate.

        Parameters
        ----------
        title : str
            The title of the tab and/or window
        widget : QWidget
            The widget to open in the dock
        """
        if shift_pressed() or not cls._instance.isVisible():
            cls.open_in_new_window(title=title, widget=widget)
        else:
            new_tab = ctrl_pressed()
            cls.add_to_dock(title=title, widget=widget, new_tab=new_tab)

    @classmethod
    def add_to_dock(cls, title: str, widget: QWidget, new_tab: bool = False):
        """
        Adds a widget to the tabbed docking area.

        Parameters
        ----------
        title : str
            The title of the tab
        widget : QWidget
            The widget to open in the dock
        new_tab : bool, optional
            If True, opens a new tab for the widget. If False, overwrites the current open tab.
            Defaults to False.
        """
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
        """
        Moves the widget from the currently opened tab into a floating window.

        The tab text will be preserved and moved to the window's title.
        """
        self = cls._instance
        if self.tab_widget.count() <= 0:
            return
        widget = self.tab_widget.currentWidget()
        self.open_in_new_window(self.tab_widget.tabText(self.tab_widget.currentIndex()), widget)

    @classmethod
    def open_in_new_window(cls, title: str, widget: QWidget):
        """
        Moves a widget into a floating window and let it be tracked by the dock.

        In contrast with a window opened by a PydmRelatedDisplay widget, this allows the floating window
        to be recalled to the dock at any time.

        Parameters
        ----------
        title : str
            The title of the window
        widget : QWidget
            The widget to open in the window
        """
        self = cls._instance
        self.clean_detached_widgets()
        if widget not in self.detached_widgets:
            self.detached_widgets.append(widget)
        widget.setParent(self)
        widget.setParent(None)  # type: ignore
        widget.setWindowTitle(title)
        cursor_pos = QCursor().pos()
        left_of_cursor = QPoint(cursor_pos.x() - 10, cursor_pos.y())
        widget.move(left_of_cursor)
        widget.show()
        widget.activateWindow()
        self.update_attach_enabled()

    @classmethod
    def reattach_user_choice(cls):
        """
        Lets the user select a widget to return to the dock in a new tab.

        If there are no eligible widgets, this does nothing.
        If there is only one eligible widget, this will return that widget to the dock.
        If there are two or more eligible widgets, this will open the attach menu, so the user can pick one widget.

        The window title will be preserved and placed in the tab's text field.
        """
        self = cls._instance
        self.clean_detached_widgets()
        if not self.detached_widgets:
            return
        elif len(self.detached_widgets) == 1:
            widget = self.detached_widgets[0]
            self.reattach_to_dock(widget=widget)
        else:
            self.show_attach_menu()

    @classmethod
    def reattach_to_dock(cls, widget: QWidget):
        """
        Reattaches a specific widget to the dock in a new tab.

        The window title will be preserved and placed in the tab's text field.

        Parameters
        ----------
        widget : QWidget
            The widget to return to the dock
        """
        self = cls._instance
        self.add_to_dock(title=widget.windowTitle(), widget=widget, new_tab=True)
        if widget in self.detached_widgets:
            self.detached_widgets.remove(widget)
        self.clean_detached_widgets()

    def show_attach_menu(self) -> QMenu:
        """
        Creates a menu at the cursor position that can be used to reattach one tracked widget to the dock.

        The window title will be preserved and placed in the tab's text field.
        """
        self.clean_detached_widgets()
        menu = QMenu(self.attach_button)
        for widget in self.detached_widgets:
            action = menu.addAction(widget.windowTitle())
            action.triggered.connect(partial(self.reattach_to_dock, widget))
        menu.popup(QCursor().pos())
        return menu

    def clean_detached_widgets(self):
        """
        Prunes the list of tracked widgets to remove any windows that the user has closed.

        Closed windows are not eligible to be reattached to the dock.
        """
        for display in list(self.detached_widgets):
            if not display.isVisible():
                self.detached_widgets.remove(display)
        self.detached_widgets = list(set(self.detached_widgets))
        self.update_attach_enabled()

    def update_attach_enabled(self):
        """
        Enables the attach button if we have any detached widgets, otherwise disables it
        """
        self.attach_button.setEnabled(bool(self.detached_widgets))

    def close_tab(self):
        """
        Removes the currently opened tab
        """
        self.tab_widget.removeTab(self.tab_widget.currentIndex())


class LucidDockButton(QPushButton):
    """
    A QPushButton that opens a PyDM screen in the dock when clicked.

    The user must set the "filename" property to the path of the screen to use,
    and may optionally set the "macro" property to the macro string used
    to substitute values into the fields.

    Parameters
    ----------
    parent : QWidget, optional
        Standard qt parent argument
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._filename: str = ""
        self._macro: str = ""
        self.clicked.connect(self.open_in_dock)
        self._icon = ifont.icon("anchor")
        self.setCursor(QCursor(self._icon.pixmap(16, 16)))  # type: ignore
        self.cached_ui_text = ""
        self.cached_widget: QWidget | None = None

    def build_widget(self) -> QWidget:
        """
        Create or re-use the widget defined by the pydm file.
        """
        fname = find_file(
            self._filename,
            raise_if_not_found=True,
        )
        fname = cast(str, fname)
        macros = parse_macro_string(self._macro)
        with open(fname, "r") as fd:
            ui_text = fd.read()

        if ui_text != self.cached_ui_text or self.cached_widget is None:
            if self.cached_widget is not None:
                clear_compiled_ui_file_cache()
                self.cached_widget.close()
            display = cast(QWidget, load_file(fname, macros=macros, target=ScreenTarget.DIALOG))
            merge_widget_stylesheet(widget=display)
            self.cached_ui_text = ui_text
            self.cached_widget = display
        else:
            display = self.cached_widget
        return display

    def open_in_dock(self):
        """
        Place the widget defined by this button into the dock.
        """
        display = self.build_widget()
        LucidDock.add_to_dock_user_choice(title=display.windowTitle(), widget=display)

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
