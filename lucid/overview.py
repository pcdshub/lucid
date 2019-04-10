"""Overview of the Experimental Area"""
from qtpy.QtCore import QEvent, Qt, Property, Slot
from qtpy.QtGui import QContextMenuEvent
from qtpy.QtWidgets import QPushButton, QMenu

from lucid import LucidMainWindow
from lucid.utils import (SnakeLayout, indicator_for_device, display_for_device,
                         suite_for_devices, reload_widget_stylesheet)


class IndicatorCell(QPushButton):
    """Single Cell of Indicator Lights in the Overview Grid"""
    max_columns = 6
    icon_size = (12, 12)

    def __init__(self, title=None, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        # Disable borders on the widget unless a hover occurs
        self.setStyleSheet('QPushButton:!hover {border: None}')
        self.setLayout(SnakeLayout(self.max_columns))
        self.layout().setContentsMargins(20, 20, 20, 20)
        self.layout().setHorizontalSpacing(2)
        self.layout().setVerticalSpacing(2)
        self.devices = []
        # References for created devices
        self._device_displays = {}
        self._suite = None
        self._selecting_widgets = list()
        # Setup Menu
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.device_menu = QMenu()
        self._displays = []
        # Click button action
        self.clicked.connect(LucidMainWindow.in_dock(
                                        self.show_devices,
                                        title=self.title,
                                        active_slot=self._devices_shown))

    @Property(bool)
    def selected(self):
        """Whether the devices in this cell have been selected"""
        return self._selecting_widgets != []

    def add_indicator(self, widget):
        """Add an indicator to the Panel"""
        widget.setFixedSize(*self.icon_size)
        widget.installEventFilter(self)
        self.layout().addWidget(widget)

    def add_device(self, device):
        """Add a device to the IndicatorCell"""
        indicator = indicator_for_device(device)
        self.devices.append(device)
        self.add_indicator(indicator)

        @Slot()
        @LucidMainWindow.in_dock(title=device.name)
        def show_device():
            if device.name not in self._device_displays:
                widget = display_for_device(device)
                widget.setParent(self)
                self._device_displays[device.name] = widget
            return self._device_displays[device.name]

        self.device_menu.addAction(device.name, show_device)

    def contextMenuEvent(self, event):
        """QWidget.contextMenuEvent to display available devices"""
        self.device_menu.exec_(self.mapToGlobal(event.pos()))

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

    def show_devices(self):
        """Create a widget for all devices found in the ``IndicatorCell``"""
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
        """Callback when correspoinding ``TyphonSuite`` is accessed"""
        # On first selection
        if shown and self not in self._selecting_widgets:
            self._selecting_widgets.append(self)
            reload_widget_stylesheet(self)
        # On closure
        elif not shown and self in self._selecting_widgets:
            self._selecting_widgets.remove(self)
            reload_widget_stylesheet(self)
