import io
import logging
import pathlib

from qtpy.QtCore import Qt
from qtpy.QtGui import QResizeEvent
from qtpy.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QSizePolicy, QSpacerItem, QTabWidget, QVBoxLayout, QWidget

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
    beamline : str
        The name of the beamline that this home screen is for
    toolbar : str, optional
        Path to toolbar file
    parent : QWidget, optional
        Standard qt parent argument
    """

    def __init__(self, beamline: str, toolbar: str | io.StringIO | None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.beamline = beamline
        self.toolbar = toolbar
        self.setup_ui()

    def setup_ui(self):
        """
        Create all the widgets that will be used in the screen
        """
        self.setWindowTitle(f"LUCID - {self.beamline}")
        self.main_widget = QWidget()
        self.grid = IndicatorGrid()
        self.dock = LucidDock()
        self.dock.set_fixed_dock_width(850)
        self.dock.grid_changed.connect(self.fixed_grid_selected)

        self.dummy_tabs = QTabWidget()
        self.dock_vis_label = QLabel()
        self.dock_vis_label.setAlignment(Qt.AlignCenter)
        self.dummy_tabs.addTab(self.dock_vis_label, "")
        self.dummy_tabs.setEnabled(False)
        self.dummy_tabs.hide()

        self.grid_hlayout = QHBoxLayout()
        self.grid_hlayout.setContentsMargins(0, 0, 0, 0)
        self.grid_hlayout.addWidget(self.grid)
        self.grid_hlayout.addWidget(self.dummy_tabs)
        self.grid_hlayout.setAlignment(self.grid, Qt.AlignLeft)

        self.left_vlayout = QVBoxLayout()
        self.left_vlayout.setContentsMargins(0, 0, 0, 0)
        self.left_vlayout.addLayout(self.grid_hlayout)
        if self.toolbar is not None:
            vertical_spacer = QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.MinimumExpanding)
            self.left_vlayout.addItem(vertical_spacer)
            self.quick_toolbar = QuickAccessToolbar()
            self.quick_toolbar.set_tools_file(self.toolbar)
            self.left_vlayout.addWidget(self.quick_toolbar)
            if self.quick_toolbar.default_dock_button is not None:
                default_docked = self.quick_toolbar.default_dock_button.build_widget()
                self.dock.add_to_dock(title=default_docked.windowTitle(), widget=default_docked)

        self.outer_hlayout = QHBoxLayout()
        self.outer_hlayout.setContentsMargins(3, 3, 3, 3)
        self.outer_hlayout.setSpacing(0)
        self.outer_hlayout.addLayout(self.left_vlayout)
        self.outer_hlayout.addWidget(self.dock)
        self.main_widget.setLayout(self.outer_hlayout)
        self.setCentralWidget(self.main_widget)

        self.width_threshold = 2200
        self.min_placeholder_space = 300

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore
        """
        Show the dock when there is room for the dock, hide it otherwise
        """
        new_width = event.size().width()
        if new_width < self.width_threshold:
            self.dock.hide()
            if new_width > self.min_placeholder_space:
                self.dock_vis_label.setText(
                    f"Small window mode: dock hidden\n(needs to be {self.width_threshold - new_width}px wider)"
                )
                self.dummy_tabs.show()
            else:
                self.dummy_tabs.hide()
        else:
            self.dock.show()
            self.dummy_tabs.hide()
        return super().resizeEvent(event)

    def finalize_window_settings(self):
        """
        Setup some dynamic sizing parameters based on what was loaded in the previous steps
        """
        grid_hint = self.grid.sizeHint()
        gridw = grid_hint.width()
        gridh = grid_hint.height()
        tabs_hint = self.quick_toolbar.sizeHint()
        tabw = tabs_hint.width()
        tabh = tabs_hint.height()
        self.width_threshold = gridw + self.dock.width() - 20
        minw = max(gridw, tabw) + 10
        minh = gridh + tabh
        self.setMinimumSize(minw, minh)
        self.min_placeholder_space = gridw + 210

    def fixed_grid_selected(self):
        """
        Once the user picks an NxN grid size, we need to adjust our sizing.
        """
        good_width = self.grid.sizeHint().width() + self.dock.width() + 5
        # Ensure the dock can be seen immediately
        self.setMinimumWidth(good_width)
        # Resize down if we're excessively big
        if self.width() > good_width + 200:
            self.resize(good_width, self.height())
