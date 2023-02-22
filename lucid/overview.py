"""Overview of the Experimental Area"""
import collections
import logging
import os
import weakref
from functools import partial

import yaml
from pydm.widgets import PyDMRelatedDisplayButton, PyDMShellCommand
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Property, QEvent, QSize, Qt
from qtpy.QtGui import QHoverEvent
from qtpy.QtWidgets import QGridLayout, QMenu, QPushButton, QWidget
from typhos.utils import reload_widget_stylesheet

import lucid

from .utils import (SnakeLayout, display_for_device, indicator_for_device,
                    suite_for_devices)

logger = logging.getLogger(__name__)


class BaseDeviceButton(QPushButton):
    """Base class for QPushButton to show devices"""
    _OPEN_ALL = "Open All"

    def __init__(self, title, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        # References for created screens
        self._device_displays = {}
        self._suite = None
        # Setup Menu
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.device_menu = QMenu()
        self.device_menu.aboutToShow.connect(self._menu_shown)

    def show_device(self, device):
        if device.name not in self._device_displays:
            widget = display_for_device(device)
            widget.setParent(self)
            self._device_displays[device.name] = widget
        return self._device_displays[device.name]

    def show_all(self):
        if len(self.devices) == 0:
            return None
        """Create a widget for contained devices"""
        if not self._suite:
            self._suite = suite_for_devices(
                self.devices, parent=self, pin=True)
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
        if self._OPEN_ALL not in menu_devices:
            show_all_devices = self._show_all_wrapper()
            self.device_menu.addAction(self._OPEN_ALL, show_all_devices)
            self.device_menu.addSeparator()
        # Add devices
        for device in self.devices:
            if device.name not in menu_devices:
                # Add to device menu
                show_device = self._show_device_wrapper(device)
                self.device_menu.addAction(device.name, show_device)

    def _show_all_wrapper(self):
        return lucid.LucidMainWindow.in_dock(
                        self.show_all,
                        title=self.title,
                        active_slot=self._devices_shown)

    def _show_device_wrapper(self, device):
        return lucid.LucidMainWindow.in_dock(
            partial(self.show_device, device),
            title=device.name)

    def eventFilter(self, obj, event):
        """
        QWidget.eventFilter to be installed on child indicators

        This is required to display the :meth:`.contextMenuEvent` even if an
        indicator is pressed.
        """
        # Filter child widgets events to show context menu
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                self._show_all_wrapper()()
                return True
            elif event.button() == Qt.LeftButton:
                if len(self.devices) == 1:
                    self._show_device_wrapper(self.devices[0])()
                else:
                    self.device_menu.exec_(self.mapToGlobal(event.pos()))
                return True
        return False


class IndicatorCell(BaseDeviceButton):
    """Single Cell of Indicator Lights in the Overview Grid"""
    max_columns = 5
    icon_size = 12
    spacing = 1
    margin = 5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disable borders on the widget unless a hover occurs
        self.setStyleSheet('QPushButton:!hover {border: None}')
        self.setLayout(SnakeLayout(self.max_columns))
        self.layout().setSpacing(self.spacing)
        self.layout().setContentsMargins(*4 * [self.margin])
        self._selecting_widgets = list()
        self.installEventFilter(self)
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
        self.layout().addWidget(widget)

    def add_device(self, device):
        """Add a device to the IndicatorCell"""
        indicator = indicator_for_device(device)
        self.devices.append(device)
        self.add_indicator(indicator)

    def sizeHint(self):
        size_per_icon = self.icon_size + self.spacing
        return QSize(self.max_columns * size_per_icon
                     + self.spacing + 2 * self.margin,
                     36)

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
        return super().eventFilter(obj, event)

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
            if cell:
                group.add_cell(cell)
        # Add cell to correct location in grid
        if cell:
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
    def __init__(self, parent=None, toolbar_file=None):
        super().__init__(parent=None)
        self.frame = QtWidgets.QFrame(parent)
        self.frame.setLayout(QtWidgets.QVBoxLayout())
        self.frame.layout().addWidget(self)

        if toolbar_file is not None:
            vertical_spacer = QtWidgets.QSpacerItem(
                10, 20, QtWidgets.QSizePolicy.Minimum,
                QtWidgets.QSizePolicy.MinimumExpanding
            )
            self.frame.layout().addItem(vertical_spacer)

            quick_toolbar = lucid.overview.QuickAccessToolbar(self.frame)
            quick_toolbar.toolsFile = toolbar_file
            self.frame.layout().addWidget(quick_toolbar)
        self.overlay = IndicatorOverlay(self.frame, self)
        self.overlay.setVisible(False)
        self.stackUnder(self.overlay)

    def add_from_dict(self, devices=None):
        rows = set()
        cols = set()
        if devices is None:
            return
        for e in devices:
            r, c = e.split('|')
            rows.add(r)
            cols.add(c)

        data = collections.OrderedDict()
        for r in sorted(rows):
            for c in sorted(cols):
                data[f"{r}|{c}"] = devices.get(f"{r}|{c}") or []

        for location, dev_list in data.items():
            stand, system = location.split("|")
            self.add_devices(dev_list, stand=stand, system=system)


class QuickAccessToolbar(QtWidgets.QWidget):
    """Tab Widget with tabs containing buttons defined via a yaml file"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._tools = None
        self._default_config = {'cols': 4}
        self._setup_ui()

    @Property(str)
    def toolsFile(self):
        return self._tools_file

    @toolsFile.setter
    def toolsFile(self, file):
        if not file:
            return
        if isinstance(file, (str, bytes, os.PathLike)):
            with open(self._tools_file) as tf:
                self._tools = yaml.full_load(tf)
        else:
            self._tools = yaml.full_load(file)
        self._assemble_tabs()

    def _setup_ui(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                           QtWidgets.QSizePolicy.Preferred)

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

            def min_scroll_size_hint(*args, **kwargs):
                return QtCore.QSize(40, 40)

            scroll_area = QtWidgets.QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(page)
            scroll_area.minimumSizeHint = min_scroll_size_hint
            self.tab.addTab(scroll_area, tab_name)

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
            except Exception as ex:
                logger.error(f'Failed to set property {prop} with '
                             f'value {val} for {tp}: {ex}')

        return btn
