import functools
import operator

from qtpy.QtWidgets import QMainWindow, QDockWidget, QStackedWidget
from qtpy.QtCore import Qt


class LucidMainWindow(QMainWindow):
    """QMainWindow for Lucid Applications"""
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

    def addDockWidget(self, area, dock):
        """Wrapped QMainWindow.addDockWidget"""
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

    @property
    def _docks(self):
        """QDockWidget children"""
        return [widget for widget in self.children()
                if isinstance(widget, QDockWidget)]
