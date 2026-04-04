"""
Dock widget definitions
"""

from functools import partial
from typing import Callable, ClassVar, cast

from pydm.display import ScreenTarget, clear_compiled_ui_file_cache, load_file
from pydm.utilities import IconFont, find_file
from pydm.utilities.macro import parse_macro_string
from pydm.utilities.stylesheet import merge_widget_stylesheet
from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QContextMenuEvent, QCursor
from qtpy.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    from qtpy.QtCore import Property  # type: ignore
except ImportError:
    from qtpy.QtCore import pyqtProperty as Property  # type: ignore

try:
    from qtpy.QtCore import pyqtSignal as Signal
except ImportError:
    from qtpy.QtCore import Signal  # type: ignore

from .utils import ctrl_pressed, shift_pressed

ifont = IconFont()

DeferredWidget = QWidget | Callable[[], QWidget]

DOCK_CONTROLS = """
This dock can hold any dockable PyDM or Typhos screen.

Buttons that have the anchor mouseover cursor are dockable.
All Typhos screens from the grid are dockable.

Click on a dockable button to replace the current tab.

Ctrl + click to open the screen in a new tab.
Shift + click to open the screen in a new window.

Right click to bring up a menu with the above options.

Click the up arrow to bring a tab into a new window.
Click the down arrow to bring a window into a new tab.

Screens that are already open will be moved instead of opened again,
unless their source files have been modified.
"""


class LucidDock(QWidget):
    """
    The right-hand widget in the main screen that other screens can be embedded within.

    This is basically a tab widget that implements some dock/undock functionality.

    It is expected but not enforced that only one LucidDock exists at a time.
    Most of the functionality is exposed as classmethods so that other code does not have
    to locate the dock singleton, instead you can reference the LucidDock class directly.

    You should usually populate the dock by calling LucidDock.add_to_dock_user_keybinds,
    which will:
    - Replace the current tab if no modifiers are held
    - Add a new tab if the ctrl modifier key is held
    - Open in a new window if the shift modifier key is held
    - Open in a new window if the dock is not visible

    or LucidDock.add_to_dock_user_menu, which does the same but with
    clickable menu options.

    Parameters
    ----------
    parent : QWidget, optional
        Standard qt parent argument
    """

    _instance: ClassVar["LucidDock"]

    grid_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        LucidDock._instance = self
        super().__init__(parent)

        self.tab_widgets: list[list[QTabWidget]] = [[]]
        self.attached_widgets: set[QWidget] = set()
        self.detached_widgets: set[QWidget] = set()

        self.fixed_dock_width = 850
        self.dock_cols = 1

        self.attach_buttons: list[QToolButton] = []

        self.settings_button = QToolButton()
        self.settings_button.setIcon(ifont.icon("anchor"))  # type: ignore
        self.settings_button.clicked.connect(self.show_settings)
        self.settings_button.setToolTip("Dock Settings")
        self.settings_widget = None

        first_tabs = self._create_subdock(settings_button=self.settings_button)
        self.tab_widgets[0].append(first_tabs)

        self.glayout = QGridLayout()
        self.glayout.addWidget(first_tabs)
        self.setLayout(self.glayout)

        self.dock_columns_spinbox = QSpinBox()
        self.dock_rows_spinbox = QSpinBox()
        self.apply_settings_button = QPushButton("Apply")

    @classmethod
    def set_fixed_dock_width(cls, width: int):
        """
        Choose the width of the individual tab widgets that make up the LucidDock widget.

        Parameters
        ----------
        width : int
            The width of the tab areas in pixels.
        """
        self = cls._instance
        self.fixed_dock_width = width
        for tab_row in self.tab_widgets:
            for tab_inst in tab_row:
                tab_inst.setFixedWidth(width)
        self.setFixedWidth((width + 9) * self.dock_cols)

    def _create_subdock(self, settings_button: QToolButton | None = None) -> QTabWidget:
        """
        Create a QTabWiget suitable for use as one of the tab docks.

        Parameters
        ----------
        settings_button : QToolButton, optional
            A settings button to add to the corner in addition to the attach button.
            This is currently used to add the dock settings button to the first dock.
        """
        tab_widget = QTabWidget()
        tab_widget.setMovable(True)
        tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab_widget.currentChanged.connect(partial(self.show_correct_tab_buttons, tab_widget=tab_widget))

        corner_widget = QWidget()
        corner_layout = QHBoxLayout()
        corner_widget.setLayout(corner_layout)
        corner_layout.setContentsMargins(0, 0, 0, 0)

        attach_button = QToolButton()
        attach_button.setIcon(ifont.icon("arrow-down"))  # type: ignore
        attach_button.clicked.connect(partial(self.reattach_user_choice, tab_widget))
        attach_button.setEnabled(False)

        self.attach_buttons.append(attach_button)

        corner_layout.addWidget(attach_button)
        if settings_button is not None:
            corner_layout.addWidget(settings_button)

        tab_widget.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)
        corner_widget.setMinimumHeight(20)

        return tab_widget

    def show_settings(self):
        """
        Show dock settings in a pop-up dialog
        """
        settings = self._get_settings_widget()
        settings.setParent(self)
        settings.setParent(None)  # type: ignore
        settings.move(QCursor().pos())
        settings.show()

    def _get_settings_widget(self) -> QWidget:
        """
        Assemble the dock settings pop-up dialog
        """
        if self.settings_widget is not None:
            return self.settings_widget

        outer_widget = QWidget()
        outer_widget.setWindowTitle("Lucid Dock Settings")
        outer_layout = QVBoxLayout()
        outer_widget.setLayout(outer_layout)

        outer_layout.addWidget(QLabel("Dock Grid Settings"))

        form_widget = QWidget()
        form_layout = QFormLayout()
        form_widget.setLayout(form_layout)
        outer_layout.addWidget(form_widget)

        form_layout.addRow("Dock Columns", self.dock_columns_spinbox)
        form_layout.addRow("Dock Rows", self.dock_rows_spinbox)
        form_layout.addRow("", self.apply_settings_button)

        self.dock_columns_spinbox.setMinimum(1)
        self.dock_columns_spinbox.setMaximum(10)
        self.dock_rows_spinbox.setMinimum(1)
        self.dock_rows_spinbox.setMaximum(10)
        self.apply_settings_button.clicked.connect(self.apply_settings)

        dock_controls_label = QLabel(DOCK_CONTROLS)
        outer_layout.addWidget(dock_controls_label)

        self.settings_widget = outer_widget
        return outer_widget

    def apply_settings(self):
        """
        Apply settings changes from the dock settings dialog.
        """
        cols = self.dock_columns_spinbox.value()
        self.dock_cols = cols
        rows = self.dock_rows_spinbox.value()
        while len(self.tab_widgets) < rows:
            self.tab_widgets.append([])
        for row_idx, tab_row in enumerate(self.tab_widgets):
            while len(tab_row) < cols:
                new_tabs = self._create_subdock()
                self.glayout.addWidget(new_tabs, row_idx, len(tab_row))
                tab_row.append(new_tabs)
            for col_idx, tab_inst in enumerate(tab_row):
                tab_inst.setVisible(bool(row_idx < rows and col_idx < cols))
        self.set_fixed_dock_width(self.fixed_dock_width)
        self.grid_changed.emit()

    def show_correct_tab_buttons(self, new_idx: int, tab_widget: QTabWidget):
        """
        Ensure that the undock/close buttons are only visible on the active tab.

        Otherwise, it's really easy to accidentally close/undock tabs when trying to change tabs.

        Parameters
        ----------
        new_idx : int
            The integer of the currently open tab. This is intended be passed by the QTabWidget's
            "currentChanged" signal.
        """
        tab_bar = tab_widget.tabBar()
        for idx in range(tab_widget.count()):
            button = tab_bar.tabButton(idx, tab_bar.ButtonPosition.RightSide)
            if button is None:
                continue
            if idx == new_idx:
                button.show()
            else:
                button.hide()

    def get_open_tab_widget(self) -> QTabWidget:
        """
        Returns the first tab widget that is empty and visible.

        If no tab widget is empty and visible, returns the first tab widget.
        """
        for tab_row in self.tab_widgets:
            for tab_inst in tab_row:
                if tab_inst.isVisible() and tab_inst.count() == 0:
                    return tab_inst
        return self.tab_widgets[0][0]

    def has_empty_tab(self) -> bool:
        """
        Returns True if any tab is empty as visible.
        """
        for tab_row in self.tab_widgets:
            for tab_inst in tab_row:
                if tab_inst.isVisible() and tab_inst.count() == 0:
                    return True
        return False

    @classmethod
    def add_to_dock_user_keybinds(cls, widget: DeferredWidget, title: str = ""):
        """
        The main way other code should add widgets to the dock.

        This checks the user's modifier keys and opens the widget in the current tab (default),
        a new tab (ctrl), or a new window (shift, or invisible dock) as appropriate.

        Parameters
        ----------
        widget : DeferredWidget
            The widget to use, or a callable to produce the widget right before it is needed.
        title : str
            The title of the tab and/or window.
            If omitted we'll use the widget's windowTitle
        """
        if shift_pressed() or not cls._instance.isVisible():
            cls.open_in_new_window(widget=widget, title=title)
        else:
            new_tab = ctrl_pressed()
            cls.add_to_dock(widget=widget, title=title, new_tab=new_tab)

    @classmethod
    def add_to_dock_user_menu(
        cls, widget: DeferredWidget, title: str = "", pos: QPoint | None = None, menu: QMenu | None = None
    ) -> QMenu:
        """
        The other main way to add widgets to the dock, with a multiple choice menu.

        Rather than using modifier keys like add_to_dock_user_keybinds, this creates
        a compact menu with each variant as an option.

        Parameters
        ----------
        widget : DeferredWidget
            The widget to use, or a callable to produce the widget right before it is needed.
        title : str, optional
            The title of the tab and/or window.
            If omitted we'll use the widget's windowTitle.
        pos : QPoint, optional
            The position to open the menu at.
            If omitted, we won't open the menu.
        menu : QMenu, optional
            If provided, we'll add actions to this menu rather than create a new menu.
            This is used to include these menus as submenus of other menus.

        Returns
        -------
        menu : QMenu
        """
        self = cls._instance
        if menu is None:
            menu = QMenu()
        self.clean_detached_widgets()
        if self.has_empty_tab():
            replace_tab_action = menu.addAction("Open in Empty Tab")
        else:
            replace_tab_action = menu.addAction("Replace Current Tab")
        replace_tab_action.triggered.connect(partial(cls.add_to_dock, widget=widget, title=title, new_tab=False))
        new_tab_action = menu.addAction("Open in New Tab")
        new_tab_action.triggered.connect(partial(cls.add_to_dock, widget=widget, title=title, new_tab=True))
        new_window_action = menu.addAction("Open in New Window")
        new_window_action.triggered.connect(partial(cls.open_in_new_window, widget=widget, title=title))
        if pos is not None:
            menu.exec_(pos)
        return menu

    @classmethod
    def add_to_dock(
        cls, widget: DeferredWidget, title: str = "", new_tab: bool = False, tab_widget: QTabWidget | None = None
    ):
        """
        Adds a widget to the tabbed docking area.

        Parameters
        ----------
        widget : DeferredWidget
            The widget to use, or a callable to produce the widget right before it is needed.
        title : str, optional
            The title of the tab and/or window.
            If omitted we'll use the widget's windowTitle.
        new_tab : bool, optional
            If True, opens a new tab for the widget. If False, overwrites the current open tab.
            Defaults to False.
        tab_widget : QTabWidget, optional
            If provided, make sure to put the widget into a specific tabbed docking area.
            Otherwise, we'll find the first open dock, or default to the first dock if all are
            occupied.
        """
        self = cls._instance
        if tab_widget is None:
            tab_widget = self.get_open_tab_widget()
        idx = None
        if not new_tab and tab_widget.count() > 0:
            idx = tab_widget.currentIndex()
            tab_widget.removeTab(idx)

        if not isinstance(widget, QWidget):
            widget = widget()
        if not title:
            title = widget.windowTitle()

        # Some typhos screens crash (segfault) when added to the tabs if not shown first (???)
        widget.show()

        if idx is None:
            idx = tab_widget.addTab(widget, title)
        else:
            tab_widget.insertTab(idx, widget, title)

        button_row = QWidget()

        detach_button = QToolButton()
        detach_button.setIcon(ifont.icon("arrow-up"))  # type: ignore
        detach_button.clicked.connect(partial(self.detach_from_dock, tab_widget))
        close_button = QToolButton()
        close_button.setIcon(ifont.icon("window-close"))  # type: ignore
        close_button.clicked.connect(partial(self.close_tab, tab_widget))

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(3, 0, 0, 0)
        hlayout.addWidget(detach_button)
        hlayout.addWidget(close_button)
        button_row.setLayout(hlayout)

        tab_bar = tab_widget.tabBar()
        tab_bar.setTabButton(idx, tab_bar.ButtonPosition.RightSide, button_row)
        tab_widget.setCurrentIndex(idx)

        self.attached_widgets.add(widget)
        try:
            self.detached_widgets.remove(widget)
        except KeyError:
            ...

    def detach_from_dock(self, tab_widget: QTabWidget):
        """
        Moves the widget from the currently opened tab into a floating window.

        The tab text will be preserved and moved to the window's title.
        """
        if tab_widget.count() <= 0:
            return
        widget = tab_widget.currentWidget()
        self.open_in_new_window(widget=widget, title=tab_widget.tabText(tab_widget.currentIndex()))

    @classmethod
    def open_in_new_window(cls, widget: DeferredWidget, title: str = ""):
        """
        Moves a widget into a floating window and let it be tracked by the dock.

        In contrast with a window opened by a PydmRelatedDisplay widget, this allows the floating window
        to be recalled to the dock at any time.

        Parameters
        ----------
        widget : DeferredWidget
            The widget to use, or a callable to produce the widget right before it is needed.
        title : str, optional
            The title of the tab and/or window.
            If omitted we'll use the widget's windowTitle.
        """
        self = cls._instance
        self.clean_detached_widgets()

        if not isinstance(widget, QWidget):
            widget = widget()
        if not title:
            title = widget.windowTitle()

        try:
            self.attached_widgets.remove(widget)
        except KeyError:
            ...
        self.detached_widgets.add(widget)
        widget.setParent(self)
        widget.setParent(None)  # type: ignore
        widget.setWindowTitle(title)
        cursor_pos = QCursor().pos()
        left_of_cursor = QPoint(cursor_pos.x() - 10, cursor_pos.y())
        widget.move(left_of_cursor)
        widget.show()
        widget.activateWindow()
        self.update_attach_enabled()

    def reattach_user_choice(self, tab_widget: QTabWidget):
        """
        Lets the user select a widget to return to the dock in a new tab.

        If there are no eligible widgets, this does nothing.
        If there is only one eligible widget, this will return that widget to the dock.
        If there are two or more eligible widgets, this will open the attach menu, so the user can pick one widget.

        The window title will be preserved and placed in the tab's text field.
        """
        self.clean_detached_widgets()
        if not self.detached_widgets:
            return
        elif len(self.detached_widgets) == 1:
            widget = list(self.detached_widgets)[0]
            self.reattach_to_dock(widget=widget, tab_widget=tab_widget)
        else:
            self.show_attach_menu(tab_widget=tab_widget, pos=QCursor().pos())

    def reattach_to_dock(self, widget: QWidget, tab_widget: QTabWidget):
        """
        Reattaches a specific widget to the dock in a new tab.

        The window title will be preserved and placed in the tab's text field.

        Parameters
        ----------
        widget : QWidget
            The widget to return to the dock
        """
        self.add_to_dock(title=widget.windowTitle(), widget=widget, new_tab=True, tab_widget=tab_widget)
        self.attached_widgets.add(widget)
        try:
            self.detached_widgets.remove(widget)
        except KeyError:
            ...
        self.clean_detached_widgets()

    def show_attach_menu(self, tab_widget: QTabWidget, pos: QPoint | None = None) -> QMenu:
        """
        Creates a menu that can be used to reattach one tracked widget to the dock.

        The window title will be preserved and placed in the tab's text field.
        """
        self.clean_detached_widgets()
        menu = QMenu()
        for widget in self.detached_widgets:
            action = menu.addAction(widget.windowTitle())
            action.triggered.connect(partial(self.reattach_to_dock, widget, tab_widget))
        if pos is not None:
            menu.exec_(pos)
        return menu

    def clean_detached_widgets(self):
        """
        Prunes the lists of tracked widgets to remove any windows that the user has closed.

        Closed windows are not eligible to be reattached to the dock.
        """
        for display in list(self.detached_widgets) + list(self.attached_widgets):
            if not display.isVisible():
                self.detached_widgets.remove(display)
        self.update_attach_enabled()

    def update_attach_enabled(self):
        """
        Enables the attach button if we have any detached widgets, otherwise disables it
        """
        for button in self.attach_buttons:
            button.setEnabled(bool(self.detached_widgets))

    def close_tab(self, tab_widget: QTabWidget):
        """
        Removes the currently opened tab
        """
        tab_widget.removeTab(tab_widget.currentIndex())


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
            display.hide()
            merge_widget_stylesheet(widget=display)
            self.cached_ui_text = ui_text
            self.cached_widget = display
        else:
            display = self.cached_widget
        return display

    def open_in_dock(self):
        """
        Place the widget defined by this button into the dock based on the key modifiers.
        """
        LucidDock.add_to_dock_user_keybinds(widget=self.build_widget)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # type: ignore
        """
        On right-click, open a menu to decide where the widget should go.
        """
        LucidDock.add_to_dock_user_menu(widget=self.build_widget, pos=event.globalPos())

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
