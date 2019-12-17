import functools
import logging
import pathlib

from PyQtAds import QtAds
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QMainWindow, QToolBar, QStyle,
                            QLineEdit, QSizePolicy, QWidget)

logger = logging.getLogger(__name__)

MODULE_PATH = pathlib.Path(__file__).parent


class LucidMainWindow(QMainWindow):
    """
    QMainWindow for LUCID Applications

    The skeleton of the LUCID application, the window consists of a static
    toolbar, a variety of central views for devices and scripts required for
    operation, and also the docking system for launching detailed windows.

    Parameters
    ----------
    parent: optional
    """
    __instance = None

    def __init__(self, parent=None):
        if self.__initialized:
            return
        self.dock_manager = None
        super().__init__(parent=parent)
        self.setup_ui()
        self.__initialized = True

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = QMainWindow.__new__(LucidMainWindow)
            cls.__instance.__initialized = False
        return cls.__instance

    def setup_ui(self):
        # Toolbar
        self.toolbar = LucidToolBar()
        self.addToolBar(Qt.TopToolBarArea, LucidToolBar())

        # Use the dockmanager for the main window - it will set itself as the
        # central widget
        self.dock_manager = QtAds.CDockManager(self)
        self.dock_manager.setStyleSheet(
            open(MODULE_PATH / 'dock_style.css', 'rt').read())

    @classmethod
    def find_window(cls, widget):
        """
        Navigate the widget hierarchy to find instance of LucidMainWindow

        Parameters
        ----------
        widget: QWidget

        Returns
        -------
        window: LucidMainWindow
        """
        parent = widget.parent()
        if isinstance(parent, cls):
            return parent
        elif parent is None:
            raise EnvironmentError("No LucidMainWindow can be found "
                                   "in widget hierarchy")
        return cls.find_window(parent)

    @classmethod
    def in_dock(cls, func=None, title=None, area=None, active_slot=None):
        """
        Wrapper to show QWidget in ``LucidMainWindow``

        This allows any widget that is contained within the ``LucidMainWindow``
        the ability to display a widget in the docking system without needing
        to have direct access to the ``LucidMainWindow`` itself.

        The widget returned **must** share a parent hierarchy with a
        ``LucidMainWindow``. See :meth:`.find_window` for more detail.

        Parameters
        ----------
        cls: ``LucidMainWindow``

        func: callable
            Method which returns a QWidget whose parentage can be traced back
            to a ``LucidMainWindow`` instance

        title: str, optional
            Title for QDockWidget. This is what will be displayed in the tab
            system

        area: ``QDockWidgetArea``, optional
            If None, this wil be the first area in
            ``LucidMainWindow.allowed_docks``

        active_slot: callable, optional
            Callable which accepts a boolean argument. This will be called when
            the widget is closed or opened. This does not include when the
            QDockWidget is hidden behind another tab in the docking system.
            This will only be connected the first time a widget is added to the
            docking system

        Example
        -------
        .. code:: python

            @LucidMainWindow.in_dock(title='My Button')
            def dock_my_button(parent):
                button = QPushButton(parent=parent)
                return button

        """
        # When the decorator is not called
        if not func:
            return functools.partial(cls.in_dock, area=area, title=title,
                                     active_slot=active_slot)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal title

            # Retrieve widget
            widget = func()
            window = LucidMainWindow()

            # Add the widget to the dock
            if not title:
                title = (widget.objectName() or
                         (widget.__class__.__name__ + hex(id(widget))[:5])
                         )

            dock = window.dock_manager.findDockWidget(title)
            if dock:
                active_slot(True)
                window.dock_manager.addDockWidgetTab(
                    QtAds.RightDockWidgetArea, dock)
                dock.toggleView(True)
                return widget

            dock = QtAds.CDockWidget(title)
            dock.setWidget(widget)
            widget.setParent(dock)
            window.dock_manager.addDockWidgetTab(
                QtAds.RightDockWidgetArea, dock)

            # Ensure the main dock is actually visible
            widget.raise_()
            widget.setVisible(True)

            if active_slot:
                # Connect dock closed callback to active_slot False
                dock.closed.connect(functools.partial(active_slot, False))
                active_slot(True)

            return widget

        return wrapper


class LucidToolBar(QToolBar):
    """LucidToolBar for LucidMainWindow"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Toolbar Configuration
        self.setMovable(False)
        self.setLayoutDirection(Qt.LeftToRight)
        # Back and Forward
        self.addAction(self.style().standardIcon(QStyle.SP_ArrowLeft),
                       'Back')
        self.addAction(self.style().standardIcon(QStyle.SP_ArrowRight),
                       'Forward')
        self.addSeparator()
        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.MinimumExpanding,
                             QSizePolicy.MinimumExpanding)
        self.addWidget(spacer)
        # Search
        edit = QLineEdit()
        edit.setPlaceholderText("Search ...")
        self.addWidget(edit)
