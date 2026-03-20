import logging
import pathlib

from qtpy.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from .dock import LucidDock
from .overview import IndicatorGridWithOverlay

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

    def __init__(self, beamline: str, toolbar: str | None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.beamline = beamline
        self.toolbar = toolbar
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"LUCID - {self.beamline}")
        self.main_widget = QWidget()
        self.grid = IndicatorGridWithOverlay(toolbar_file=self.toolbar)
        self.dock = LucidDock()
        self.dock.setFixedHeight(1000)
        self.dock.setFixedWidth(850)
        self.hlayout = QHBoxLayout()
        self.hlayout.addWidget(self.grid.frame)
        self.hlayout.addWidget(self.dock)
        self.main_widget.setLayout(self.hlayout)
        self.setCentralWidget(self.main_widget)

