import logging

from pydm.widgets import PyDMDrawingCircle
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QGridLayout
from typhon import TyphonDeviceDisplay, TyphonSuite

logger = logging.getLogger(__name__)


class SnakeLayout(QGridLayout):
    """
    Snaking Layout

    The size is the maximum number of widgets before beginning the next row or
    column. The direction specifies whether the grid pattern will be filled
    column first, or row first.

    Parameters
    ----------
    widgets: Iterable
        List of widgets to place in grid

    size: int
        Maximum size of row or column

    direction: Qt.Direction, optional
        Whether the layout is filled column or row first.

    Returns
    -------
    QGridLayout
        Filled with widgets provided in function call

    Example
    -------
    .. code:: python

        # Three rows
        gridify(widgets, 3, direction=Qt.Vertical)

        # Five columns
        gridify(widgets, 5, direction=Qt.Vertical)  # Default direction

    """
    def __init__(self, size, direction=Qt.Horizontal):
        super().__init__()
        self.size = int(size)
        self.direction = direction

    def addWidget(self, widget):
        """Add a QWidget to the layout"""
        # Number of widgets already existing
        position = self.count()
        # Desired position based on current count
        grid_position = [position / self.size, position % self.size]
        # Start vertically if desired
        if self.direction == Qt.Vertical:
            grid_position.reverse()
        # Add to layout
        super().addWidget(widget,
                          grid_position[0],
                          grid_position[1])


def indicator_for_device(device):
    """Create a QWidget to indicate the alarm state of a QWidget"""
    # This is a placeholder. There will be a system for determining the mapping
    # of Device to icon put in place
    circle = PyDMDrawingCircle()
    circle.setStyleSheet('PyDMDrawingCircle '
                         '{border: none; '
                         ' background: transparent;'
                         ' qproperty-penColor: black;'
                         ' qproperty-penWidth: 2;'
                         ' qproperty-penStyle: SolidLine;'
                         ' qproperty-brush: rgba(0,220,0,120);} ')
    return circle


def display_for_device(device, display_type=None):
    """Create a TyphonDeviceDisplay for a given device"""
    logger.debug("Creating device display for %r", device)
    display = TyphonDeviceDisplay.from_device(device)
    if display_type:
        display.display_type = display_type
    return display


def suite_for_devices(devices):
    """Create a TyphonSuite to display multiple devices"""
    suite = TyphonSuite()
    for device in devices:
        suite.add_device(device)
    return suite
