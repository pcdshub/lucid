from __future__ import annotations

from typing import Optional

from qtpy import QtWidgets

from . import utils

try:
    import PyQtAds
    from PyQtAds import QtAds
except ImportError:
    QtAds = None
    PyQtAds = None


class DockWidget:
    dock: QtWidgets.QFrame | QtAds.CDockWidget
    _using_ads: bool

    def __init__(
        self,
        title: str,
        closable: bool = True,
        floatable: bool = True,
        movable: bool = True,
        min_size_hint_from_contents: bool = True,
    ):
        super().__init__()
        if QtAds is None:
            self._using_ads = False
            self._dock = QtWidgets.QFrame()
            self._dock.setWindowTitle(title)
            self._dock.setLayout(QtWidgets.QVBoxLayout())
        else:
            self._using_ads = True
            self._dock = QtAds.CDockWidget(title)
            self._dock.setToggleViewActionMode(QtAds.CDockWidget.ActionModeShow)
            self._dock.setFeature(self._dock.DockWidgetClosable, closable)
            self._dock.setFeature(self._dock.DockWidgetFloatable, floatable)
            self._dock.setFeature(self._dock.DockWidgetMovable, movable)
            if min_size_hint_from_contents:
                self._dock.setMinimumSizeHintMode(QtAds.CDockWidget.MinimumSizeHintFromContent)

    def set_widget(self, widget: QtWidgets.QWidget, force_no_scroll: bool = True):
        if not self._using_ads:
            self._dock.layout().addWidget(widget)
        else:
            flags = 0
            if force_no_scroll:
                flags |= self._dock.eInsertMode.ForceNoScrollArea
            self._dock.setWidget(widget, flags)
            widget.setParent(self._dock)

    def is_floating(self) -> bool:
        if self._dock is None:
            return False
        return self._dock.isFloating()

    def show(self):
        self._dock.show()

    def is_in_floating_container(self) -> bool:
        if self._dock is None:
            return False
        return self._dock.isInFloatingContainer()

    def toggle_view(self, visible: bool):
        if self._dock is None:
            return

        self._dock.toggleView(True)

    def windowTitle(self) -> str:
        return self._dock.windowTitle()

    def __getattr__(self, attr: str):
        return getattr(self._dock, attr)


class DockManager:
    _manager: QtWidgets.QWidget | QtAds.CDockManager
    _widgets: list[DockWidget]

    def __init__(self, parent: QtWidgets.QWidget, dark: bool = False):
        super().__init__()
        self._widgets = []
        if QtAds is None:
            self._using_ads = False
            self._manager = QtWidgets.QWidget()
            parent.setCentralWidget(self._manager)
        else:
            self._using_ads = True
            self._manager = QtAds.CDockManager(parent)

            stylesheet_filename = ('dock_style_dark.css' if dark else 'dock_style.css')
            with open(utils.MODULE_PATH / stylesheet_filename) as fp:
                self._manager.setStyleSheet(fp.read())

    def add_dock_widget(self, location: str, widget: DockWidget | QtAds.CDockWidget):
        if not self._using_ads:
            self._widgets.append(widget)
            # widget.destroyed.connect(self._remove_widget)
            widget.show()
            return

        assert QtAds is not None

        if isinstance(widget, DockWidget):
            dock = widget._dock
        else:
            dock = widget

        loc = {
            "left": QtAds.LeftDockWidgetArea,
            "right": QtAds.RightDockWidgetArea,
            "top": QtAds.TopDockWidgetArea,
            "bottom": QtAds.BottomDockWidgetArea,
        }[location]
        self._manager.addDockWidget(loc, dock)

    def add_dock_widget_tab(self, location: str, widget: DockWidget | QtAds.CDockWidget):
        if not self._using_ads:
            if widget not in self._widgets:
                self._widgets.append(widget)
            # widget.destroyed.connect(self._remove_widget)
            widget.show()
            return

        assert QtAds is not None

        if isinstance(widget, DockWidget):
            dock = widget._dock
        else:
            dock = widget

        loc = {
            "left": QtAds.LeftDockWidgetArea,
            "right": QtAds.RightDockWidgetArea,
            "top": QtAds.TopDockWidgetArea,
            "bottom": QtAds.BottomDockWidgetArea,
        }[location]
        self._manager.addDockWidgetTab(loc, dock)

    def find_dock_widget_by_title(self, title: str) -> Optional[DockWidget]:
        if not self._using_ads:
            for widget in self._widgets:
                if widget.windowTitle() == title:
                    return widget
            return None

        return self._manager.findDockWidget(title)

    def name_to_dock_widget(self) -> dict[str, DockWidget | QtAds.CDockWidget]:
        if not self._using_ads:
            return {widget.windowTitle(): widget for widget in self._widgets}
        return self._manager.dockWidgetsMap()

    def redock(self, area: str, title: str) -> Optional[DockWidget | QtAds.CDockWidget]:
        dock = self.name_to_dock_widget().get(title, None)
        if dock is None:
            return None

        if not self._using_ads:
            dock.setVisible(True)
            dock.raise_()
        else:
            if dock.isFloating():
                self.add_dock_widget_tab(area, dock)
            dock.toggleView(True)

        return dock

    def gather(self):
        if not self._using_ads:
            for widget in self._widgets:
                widget.show()
                widget.raise_()
            return

        assert QtAds is not None
        for name, dock_widget in self._manager.dockWidgetsMap().items():
            if name in ('Grid', 'Quick Launcher Toolbar'):
                continue

            if dock_widget.isFloating():
                self._manager.addDockWidget(QtAds.RightDockWidgetArea, dock_widget)
            elif dock_widget.isInFloatingContainer():
                container = dock_widget.dockContainer()
                for dock_widget in container.dockWidgets():
                    self._manager.addDockWidget(QtAds.RightDockWidgetArea, dock_widget)
