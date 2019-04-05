import functools
import logging
import operator

from qtpy.QtWidgets import (QMainWindow, QDockWidget, QStackedWidget,
                            QToolBar, QStyle, QLineEdit, QSizePolicy,
                            QWidget)
from qtpy.QtCore import Qt

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

    def __init__(self, *args):
        super().__init__(*args)
        # This means when multiple docks are pulled into an area, we create a
        # tab system. Splitting docks is still possible through API
        self.setDockOptions(self.AnimatedDocks | self.ForceTabbedDocks)
        self.setCentralWidget(QStackedWidget())
        # Adjust corners
        self.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        # Add toolbar
        self.addToolBar(Qt.TopToolBarArea, LucidToolBar())

    def addDockWidget(self, area, dock):
        """
        Wrapped QMainWindow.addDockWidget

        Add a QDockWidget to the LucidMainWindow. This is necessary in order to
        force the tabbed behavior desired in the window. In addition it
        performs the basic setup so the QDockWidget can be dragged to the
        proper areas of the window, and also sets the focus on the dock so it
        is immediately visible. This should rarely be called by external
        users instead use the :meth:`.in_dock` decorator.

        Parameters
        ----------
        area: Qt.DockWidgetArea

        dock: QDockWidget
        """
        # Force the dockwidget to only be allowed in areas determined by the
        # LucidMainWindow.allowed_docks
        allowed_flags = functools.reduce(operator.or_, self.allowed_docks)
        dock.setAllowedAreas(allowed_flags)
        super().addDockWidget(area, dock)
        # If we already have an embedded dock, add it to existing dock. This
        # needs to exist because even with ForceTabbedDocks the dock will be
        # split if we add with regular API
        embedded_docks = [curr_dock for curr_dock in self._docks
                          if self.dockWidgetArea(curr_dock) == area
                          and curr_dock.isVisible()]
        if embedded_docks:
            super().tabifyDockWidget(embedded_docks[0], dock)
        # Raise to visible
        dock.show()
        dock.raise_()
        dock.setFocus()

    @property
    def _docks(self):
        """QDockWidget children"""
        return [widget for widget in self.children()
                if isinstance(widget, QDockWidget)]

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
    def in_dock(cls, func=None, area=None):
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
        # Use first allowed area if None supplied
        area = area or cls.allowed_docks[0]
        # When the decorator is not called
        if not func:
            return functools.partial(cls.in_dock, area=area)

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
                # Create a DockWidget
                dock = QDockWidget()
                dock.setWidget(widget)
                window.addDockWidget(area, dock)
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
