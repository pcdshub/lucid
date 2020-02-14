"""Overview of the Experimental Area"""
import os
import yaml
import weakref
import logging
from functools import partial

from qtpy import QtWidgets, QtGui, QtCore
from qtpy.QtCore import QEvent, Qt, Property, QSize
from qtpy.QtGui import QContextMenuEvent, QHoverEvent
from qtpy.QtWidgets import (QPushButton, QMenu, QGridLayout, QWidget)
from typhos.utils import reload_widget_stylesheet

from pydm.widgets import PyDMShellCommand, PyDMRelatedDisplayButton

import lucid
from .utils import (SnakeLayout, indicator_for_device, display_for_device,
                    suite_for_devices)

logger = logging.getLogger(__name__)


class BaseDeviceButton(QPushButton):
    """Base class for QPushButton to show devices"""

    def __init__(self, title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        # References for created screens
        self._device_displays = {}
        self._suite = None
        # Click button action
        self.clicked.connect(lucid.LucidMainWindow.in_dock(
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
            self._suite = suite_for_devices(self.devices, parent=self)
        else:
            # Check that any devices that have been added since our last show
            # request have been added to the TyphosSuite
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
                show_device = lucid.LucidMainWindow.in_dock(
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

    @property
    def matchable_names(self):
        """All names used for text searching"""
        return [self.title] + [device.name for device in self.devices]

    @Property(bool)
    def selected(self):
        """Whether the devices in this cell have been selected"""
        return len(self._selecting_widgets)

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
        """Callback when corresponding ``TyphosSuite`` is accessed"""
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

    def __init__(self, *args, orientation, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(str(self.title))
        self.cells = []
        self.installEventFilter(self)
        self.orientation = orientation

    def add_cell(self, cell):
        self.cells.append(cell)

    @property
    def devices(self):
        """All devices contained in the ``IndicatorGroup``"""
        return [device for cell in self.cells for device in cell.devices]

    @property
    def device_to_indicator(self):
        """Dictionary of Device to IndicatorCell"""
        return {device: cell
                for cell in self.cells
                for device in cell.devices
                }

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
            '''\
QWidget[selected="true"] {background-color: rgba(20, 140, 210, 150);}
            ''')

    @property
    def groups(self):
        'A dictionary of name to IndicatorGroup'
        return dict(self._groups)

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
        group = IndicatorGroup(title=group,
                               orientation='row' if as_row else 'column')
        self._groups[group.title] = group
        # Find the correct position
        if as_row:
            (row, column) = (0, self.layout().columnCount())
        else:
            (row, column) = (self.layout().rowCount(), 0)
        self.layout().addWidget(group, row, column, Qt.AlignVCenter)


class IndicatorOverlay(QWidget):
    def __init__(self, parent, grid):
        super().__init__(parent)

        self.grid = grid
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.cell_to_percentage = weakref.WeakKeyDictionary()

    def paintEvent(self, ev):
        self.resize(self.grid.size())

        dpr = self.grid.devicePixelRatioF()
        buffer = QtGui.QPixmap(self.grid.width() * dpr,
                               self.grid.height() * dpr)
        buffer.setDevicePixelRatio(dpr)

        buffer.fill(Qt.transparent)

        painter = QtGui.QPainter()

        def cell_to_radius():
            for name, group in self.grid._groups.items():
                for cell in group.cells:
                    diameter = max((cell.width(), cell.height()))
                    radius = diameter / 2

                    cell_rect = cell.rect()
                    cell_rect.moveTopLeft(cell.pos())
                    center_pos = cell_rect.center()

                    cx = center_pos.x() - radius
                    cy = center_pos.y() - radius
                    cell_rect = QtCore.QRectF(cx, cy, diameter, diameter)
                    percent = self.cell_to_percentage.get(cell, 0.0)
                    if percent > draw_threshold:
                        percent = ((percent - draw_threshold) /
                                   (1 - draw_threshold))
                        yield cell, cell_rect, radius, percent

        painter.begin(buffer)
        painter.setRenderHint(painter.Antialiasing)

        painter.setBackgroundMode(Qt.TransparentMode)
        painter.fillRect(buffer.rect(), QtGui.QColor(0, 0, 0, 127))

        pen_size = 40
        try:
            max_percent = max(self.cell_to_percentage.values())
        except ValueError:
            max_percent = 0.0

        draw_threshold = max_percent * 0.8

        for cell, cell_rect, radius, percent in cell_to_radius():
            gradient = QtGui.QRadialGradient(cell_rect.center(), radius)
            if percent >= 0.95:
                color = (0, 1, 0, 1.0)
            else:
                color = (1, 1, 1, percent)

            gradient.setColorAt(0.7, QtGui.QColor.fromRgbF(*color))
            gradient.setColorAt(1, QtGui.QColor.fromRgbF(0, 0, 0, 0))

            brush = QtGui.QBrush(gradient)
            pen = QtGui.QPen(brush, pen_size)
            painter.setPen(pen)
            painter.drawEllipse(cell_rect)

        painter.setCompositionMode(painter.CompositionMode_Clear)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.transparent)

        for cell, cell_rect, radius, percent in cell_to_radius():
            margin = max(((1.0 - percent) * (pen_size / 2),
                          5))
            inner_ellipse = cell_rect.marginsRemoved(
                QtCore.QMarginsF(margin, margin, margin, margin))
            painter.drawEllipse(inner_ellipse)

        painter.end()

        painter.begin(self)
        painter.setCompositionMode(painter.CompositionMode_SourceOver)
        painter.drawPixmap(self.rect(), buffer, buffer.rect())
        painter.end()


class IndicatorGridWithOverlay(IndicatorGrid):
    def __init__(self, parent=None):
        super().__init__(parent=None)
        self.frame = QtWidgets.QFrame(parent)
        self.frame.setLayout(QtWidgets.QVBoxLayout())
        self.frame.layout().addWidget(self)

        verticalSpacer = QtWidgets.QSpacerItem(10, 10,
                                               QtWidgets.QSizePolicy.Minimum,
                                               QtWidgets.QSizePolicy.Expanding)
        self.frame.layout().addItem(verticalSpacer)

        self.overlay = IndicatorOverlay(self.frame, self)
        self.overlay.setVisible(False)
        self.stackUnder(self.overlay)

    def add_from_dict(self, items):
        for location, dev_list in items.items():
            stand, system = location.split("|")
            self.add_devices(dev_list, stand=stand, system=system)


class QuickAccessToolbar(QtWidgets.QWidget):
    """Tab Widget with tabs containing buttons defined via a yaml file"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._tools = None
        self._default_config = {'cols': 4}
        self._setup_ui()

    def sizeHint(self):
        return QtCore.QSize(100, 100)

    @Property(str)
    def toolsFile(self):
        return self._tools_file

    @toolsFile.setter
    def toolsFile(self, file):
        if not file:
            return
        if isinstance(file, (str, bytes, os.PathLike)):
            with open(self._tools_file, 'r') as tf:
                self._tools = yaml.full_load(tf)
        else:
            self._tools = yaml.full_load(file)
        self._assemble_tabs()

    def _setup_ui(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                           QtWidgets.QSizePolicy.Minimum)

        main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(main_layout)
        self.tab = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tab)

    def _assemble_tabs(self):
        self.tab.clear()
        for tab_name, tab_params in self._tools.items():
            page = QtWidgets.QWidget()

            config = dict(self._default_config)
            config.update(tab_params.get('config', {}))

            cols = config.get('cols', 4)
            page.setLayout(SnakeLayout(cols))

            buttons = tab_params.get('buttons', {})
            for button_text, button_config in buttons.items():
                button_widget = self._button_factory(button_text,
                                                     button_config)
                page.layout().addWidget(button_widget)
            self.tab.addTab(page, tab_name)

    def _button_factory(self, text, config):
        tp = config.pop('type')
        btn = QPushButton()
        if tp == 'shell':
            btn = PyDMShellCommand()
            btn.showIcon = False
            btn.setText(text)
        elif tp == 'display':
            btn = PyDMRelatedDisplayButton()
            btn.showIcon = False
            btn.setText(text)

        for prop, val in config.items():
            try:
                setattr(btn, prop, val)
            except Exception:
                logger.error(f'Failed to set property {prop} with '
                             f'value {val} for {tp}: {exception_text}')

        return btn
