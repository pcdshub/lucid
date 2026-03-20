import io
import logging
import pathlib

from qtpy.QtGui import QResizeEvent
from qtpy.QtWidgets import QHBoxLayout, QMainWindow, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget

from .dock import LucidDock
from .overview import IndicatorGrid, QuickAccessToolbar

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
    toolbar: str
        Path to toolbar file
    parent: optional
    """

    def __init__(self, beamline: str, toolbar: str | io.StringIO | None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.beamline = beamline
        self.toolbar = toolbar
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"LUCID - {self.beamline}")
        # Laptop Size
        self.setMinimumSize(1536, 765)
        # Hutch Computer Size
        self.setMaximumSize(2400, 1020)
        self.main_widget = QWidget()
        self.grid = IndicatorGrid()
        self.vlayout = QVBoxLayout()
        self.vlayout.addWidget(self.grid)
        if self.toolbar is not None:
            vertical_spacer = QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.MinimumExpanding)
            self.vlayout.addItem(vertical_spacer)
            self.quick_toolbar = QuickAccessToolbar()
            self.quick_toolbar.set_tools_file(self.toolbar)
            self.quick_toolbar.setFixedWidth(1500)
            self.vlayout.addWidget(self.quick_toolbar)
        self.dock = LucidDock()
        self.dock.setFixedHeight(1000)
        self.dock.setFixedWidth(850)
        self.hlayout = QHBoxLayout()
        self.hlayout.addLayout(self.vlayout)
        self.hlayout.addWidget(self.dock)
        self.main_widget.setLayout(self.hlayout)
        self.setCentralWidget(self.main_widget)

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore
        """
        Show the dock when there is room for the dock, hide it otherwise
        """
        new_size = event.size()
        if new_size.height() < 1000 or new_size.width() < 2200:
            self.dock.hide()
        else:
            self.dock.show()
        return super().resizeEvent(event)
