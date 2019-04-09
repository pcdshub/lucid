import functools
import logging
import operator

from qtpy.QtWidgets import (QMainWindow, QDockWidget, QStackedWidget,
                            QToolBar, QStyle, QLineEdit, QSizePolicy,
                            QWidget, QApplication)
from qtpy.QtGui import QCursor
from qtpy.QtCore import Qt, Signal, QPoint
from PyQtAds import QtAds

logger = logging.getLogger(__name__)


class LucidMainWindow(QMainWindow):
    """
    QMainWindow for LUCID Applications

    The skeleton of the LUCID application, the window consists of a static
    toolbar, a variety of central views for devices and scripts required for
    operation, and also the docking system for launching detailed windows.

    Attributes
    ----------
    allowed_docks: tuple
        ``Qt.DockWidgetAreas`` that accept QWidgets

    Parameters
    ----------
    parent: optional
    """
    allowed_docks = (Qt.RightDockWidgetArea, )

    def __init__(self, parent=None):
        self.main_dock = None
        self.dock_manager = None
        super().__init__(parent=parent)
        self.setup_ui()

    def setup_ui(self):
        # This means when multiple docks are pulled into an area, we create a
        # tab system. Splitting docks is still possible through API
        # Adjust corners
        self.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        # Central Widget
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)
        # Toolbar
        self.toolbar = LucidToolBar()
        self.addToolBar(Qt.TopToolBarArea, LucidToolBar())

    def setup_dock(self):
        """Setup the PyQtAds system inside a standard Qt DockWidget"""
        # If we've already loaded the docking system just return the active one
        if self.main_dock:
            return self.main_dock
        # Docked DockWidget
        self.main_dock = QDockWidget()
        # Force the dockwidget to only be allowed in areas determined by the
        # LucidMainWindow.allowed_docks
        allowed_flags = functools.reduce(operator.or_, self.allowed_docks)

        self.main_dock.setAllowedAreas(allowed_flags)
        # Place the dockmanager inside the dock
        self.dock_manager = QtAds.DockManager(self.main_dock)
        self.main_dock.setWidget(self.dock_manager)
        self.main_dock.closed.connect(self._dock_closed)
        # Add to the first allowed location
        self.addDockWidget(self.allowed_docks[0], self.main_dock)
        return self.main_dock

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
    def in_dock(cls, func=None):
        """
        Wrapper to show QWidget in ``LucidMainWindow``

        This allows any widget that is contained within the ``LucidMainWindow``
        the ability to display a widget in the docking system without needing
        to have direct access to the ``LucidMainWindow`` itself.

        The widget returned **must** share a parent hierarchy with a
        ``LucidMainWindow``. See :meth:`.find_window` for more detail.

        Example
        -------
        .. code:: python

            @LucidMainWindow.in_dock
            def dock_my_button(parent):
                button = QPushButton(parent=parent)
                return button
        """
        # When the decorator is not called
        if not func:
            return functools.partial(cls.in_dock)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Retrieve widget
            widget = func()
            try:
                window = cls.find_window(widget)
            except AttributeError:
                logger.error("Method %r was expected to return a QObject. "
                             "Instead, %r was received.",
                             func.__name__, widget)
            except EnvironmentError:
                logger.error("No LucidMainWindow found! Unable to "
                             "embed %r in dock", widget)
                # Escape hatch to display the widget that was created even
                # if a LucidMainWindow has not been created yet. Launch as a
                # QDialog
                widget.setWindowFlags(Qt.Dialog)
                widget.show()
            else:
                # Create the dock if not already exists
                window.setup_dock()
                # Add the widget to the dock
                dock = QtAds.DockWidget(widget.objectName())
                dock.set_widget(widget)
                window.dock_manager.add_dock_widget_tab(
                    QtAds.DockWidgetArea.center, dock)
            return widget

        return wrapper

    def _dock_closed(self):
        """Handle closures of the docking system"""
        # If the user closes the docking system clean up our internal state
        if self.main_dock and self.dock_manager:
            self.dock_manager.deleteLater()
            self.dock_manager = None
            self.main_dock = None


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
