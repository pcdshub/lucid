"""Overview of the Experimental Area"""
from functools import partial

from qtpy.QtCore import QEvent, Qt, Property, QSize
from qtpy.QtGui import QContextMenuEvent, QHoverEvent
from qtpy.QtWidgets import (QPushButton, QMenu, QGridLayout, QWidget)
from typhon.utils import reload_widget_stylesheet

from lucid import LucidMainWindow
from lucid.utils import (SnakeLayout, indicator_for_device, display_for_device,
                         suite_for_devices)


class BaseDeviceButton(QPushButton):
    """Base class for QPushButton to show devices"""

    def __init__(self, title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        # References for created screens
        self._device_displays = {}
        self._suite = None
        # Click button action
        self.clicked.connect(LucidMainWindow.in_dock(
            self.show_all,
            title=self.title,
            active_slot=self._devices_shown))
        # Setup Menu
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.device_menu = QMenu()
        self.device_menu.aboutToShow.connect(self._menu_shown)

    def contextMenuEvent(self, event):
        """QWidget.contextMenuEvent to display available devices"""
        self.device_menu.exec_(self.mapToGlobal(event.pos()))

    def show_device(self, device):
        if device.name not in self._device_displays:
            widget = display_for_device(device)
            widget.setParent(self)
            self._device_displays[device.name] = widget
        return self._device_displays[device.name]

    def show_all(self):
        """Create a widget for contained devices"""
        if not self._suite:
            self._suite = suite_for_devices(self.devices)
            self._suite.setParent(self)
        else:
            # Check that any devices that have been added since our last show
            # request have been added to the TyphonSuite
            for device in self.devices:
                if device not in self._suite.devices:
                    self._suite.add_device(device)
        return self._suite

    def _devices_shown(self, shown):
        """Implemeted by subclass"""
        pass

    def _menu_shown(self):
        # Current menu options
        menu_devices = [action.text()
                        for action in self.device_menu.actions()]
        # Add devices
        for device in self.devices:
            if device.name not in menu_devices:
                # Add to device menu
                show_device = LucidMainWindow.in_dock(
                    partial(self.show_device, device),
                    title=device.name)
                self.device_menu.addAction(device.name, show_device)


class IndicatorCell(BaseDeviceButton):
    """Single Cell of Indicator Lights in the Overview Grid"""
    max_columns = 6
    icon_size = 12
    spacing = 2
    margin = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disable borders on the widget unless a hover occurs
        self.setStyleSheet('QPushButton:!hover {border: None}')
        self.setLayout(SnakeLayout(self.max_columns))
        self.layout().setSpacing(self.spacing)
        self.layout().setContentsMargins(*4 * [self.margin])
        self._selecting_widgets = list()
        self.devices = list()

    @Property(bool)
    def selected(self):
        """Whether the devices in this cell have been selected"""
        return self._selecting_widgets != []

    def add_indicator(self, widget):
        """Add an indicator to the Panel"""
        widget.setFixedSize(self.icon_size, self.icon_size)
        widget.setMinimumSize(self.icon_size, self.icon_size)
        widget.installEventFilter(self)
        self.layout().addWidget(widget)

    def add_device(self, device):
        """Add a device to the IndicatorCell"""
        indicator = indicator_for_device(device)
        self.devices.append(device)
        self.add_indicator(indicator)

    def eventFilter(self, obj, event):
        """
        QWidget.eventFilter to be installed on child indicators

        This is required to display the :meth:`.contextMenuEvent` even if an
        indicator is pressed.
        """
        # Filter child widgets events to show context menu
        right_button = (event.type() == QEvent.MouseButtonPress
                        and event.button() == Qt.RightButton)
        if right_button:
            position = obj.mapToParent(event.pos())
            context_event = QContextMenuEvent(QContextMenuEvent.Mouse,
                                              position)
            self.contextMenuEvent(context_event)
            return True
        # False means do not filter
        return False

    def sizeHint(self):
        size_per_icon = self.icon_size + self.spacing
        return QSize(self.max_columns * size_per_icon
                     + self.spacing + 2 * self.margin,
                     70)

    def _devices_shown(self, shown, selector=None):
        """Callback when corresponding ``TyphonSuite`` is accessed"""
        selector = selector or self
        # On first selection
        if shown and selector not in self._selecting_widgets:
            self._selecting_widgets.append(selector)
            reload_widget_stylesheet(self)
        # On closure
        elif not shown and selector in self._selecting_widgets:
            self._selecting_widgets.remove(selector)
            reload_widget_stylesheet(self)


class IndicatorGroup(BaseDeviceButton):
    """QPushButton to select an entire row or column of devices"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(str(self.title))
        self.cells = []
        self.installEventFilter(self)

    def add_cell(self, cell):
        self.cells.append(cell)

    @property
    def devices(self):
        """All devices contained in the ``IndicatorGroup``"""
        return [device for cell in self.cells for device in cell.devices]

    def eventFilter(self, obj, event):
        """Share QHoverEvents with all cells in the group"""
        if isinstance(event, QHoverEvent):
            for cell in self.cells:
                cell.event(event)
                return False
        return False

    def _devices_shown(self, shown):
        """Selecting this button, selects all contained cells"""
        for cell in self.cells:
            cell._devices_shown(shown, selector=self)


class IndicatorGrid(QWidget):
    """GridLayout of all Indicators"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setLayout(QGridLayout())
        self.layout().setSpacing(0)
        self.layout().setSizeConstraint(QGridLayout.SetFixedSize)
        self._groups = dict()
        self.setStyleSheet(
            'QWidget[selected="true"] '
            '{background-color: rgba(20, 140, 210, 150)}')

    def add_devices(self, devices, system=None, stand=None):
        # Create cell
        cell = IndicatorCell(title=f'{stand} {system}')
        for device in devices:
            cell.add_device(device)
        # Add to proper location in grid
        coords = []
        for i, group_name in enumerate((system, stand)):
            # Create the group if not present
            if group_name not in self._groups:
                self._add_group(group_name, bool(i))
            # Add cell to group
            # Coordinate of group
            group = self._groups[group_name]
            idx = self.layout().indexOf(group)
            coords.append(self.layout().getItemPosition(idx)[i])
            group.add_cell(cell)
        # Add cell to correct location in grid
        self.layout().addWidget(cell, *coords, Qt.AlignTop)

    def _add_group(self, group, as_row):
        # Add to layout
        group = IndicatorGroup(title=group)
        self._groups[group.title] = group
        # Find the correct position
        if as_row:
            (row, column) = (0, self.layout().columnCount())
        else:
            (row, column) = (self.layout().rowCount(), 0)
        self.layout().addWidget(group, row, column, Qt.AlignVCenter)
