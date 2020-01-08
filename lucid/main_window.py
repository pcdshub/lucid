import functools
import logging
import pathlib
import re

import happi
import lucid
import typhon

from PyQtAds import QtAds
from qtpy import QtCore, QtWidgets, QtGui
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (QMainWindow, QToolBar, QStyle, QSizePolicy,
                            QWidget)

from .utils import fuzzy_match, display_for_device, get_happi_client


logger = logging.getLogger(__name__)

MODULE_PATH = pathlib.Path(__file__).parent


class LucidMainWindowMenu(QtWidgets.QMenuBar):
    settings_changed = Signal(dict)
    exit_request = Signal()
    search_overlay_changed = Signal(bool)

    def __init__(self, parent, *, settings=None):
        super().__init__(parent)
        self.main = parent

        if settings is None:
            settings = {}

        self.settings = dict(settings)
        self.actions = {}
        self._create_menu()

    def _create_menu(self):
        # File
        self.file_menu = self.addMenu('&File')
        # - Exit
        self.exit = self.file_menu.addAction('E&xit')

        # Options
        self.options_menu = self.addMenu('&Options')
        # - Search overlay
        self.add_checkable_action('Search &overlay', 'search_overlay')

    def add_checkable_action(self, label, settings_key, *, default=True):
        '''
        Add a checkable action

        Parameters
        ----------
        label : str
            The action label
        settings_key : str
            The settings dictionary key
        default : bool, optional
            The default checked state
        '''
        action = QtWidgets.QAction(label)
        self.actions[settings_key] = action

        action.setCheckable(True)
        self.settings[settings_key] = default
        action.setChecked(self.settings[settings_key])

        def set_option(value):
            logger.debug('Setting %r to %s', settings_key, value)
            setattr(self, settings_key, value)

        action.toggled.connect(set_option)
        self.options_menu.addAction(action)

    def _settings_property(key):
        'Property factory which updates the settings dict + emits changes'
        def fget(self):
            return self.settings[key]

        def fset(self, value):
            action = self.actions[key]
            if value in (True, False):
                action.setChecked(value)

            old_value = self.settings.get(key, None)
            self.settings[key] = value
            if old_value is None or value != old_value:
                signal = getattr(self, f'{key}_changed', None)
                if signal is not None:
                    signal.emit(value)
                self.settings_changed.emit(dict(self.settings))

        return property(fget, fset)

    search_overlay = _settings_property('search_overlay')


class LucidMainWindow(QMainWindow):
    """
    QMainWindow for LUCID Applications

    The skeleton of the LUCID application, the window consists of a static
    toolbar, a variety of central views for devices and scripts required for
    operation, and also the docking system for launching detailed windows.

    LucidMainWindow is a singleton - i.e., there can be only one.

    Parameters
    ----------
    parent: optional
    """
    __instance = None
    escape_pressed = Signal()

    def __init__(self, parent=None):
        if self.__initialized:
            return
        self.dock_manager = None
        super().__init__(parent=parent)
        self.setup_ui()
        self.__initialized = True

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = QMainWindow.__new__(LucidMainWindow)
            cls.__instance.__initialized = False
        return cls.__instance

    @classmethod
    def get_instance(cls):
        'The LucidMainWindow singleton instance'
        return cls.__instance

    def setup_ui(self):
        # Menu
        self.menu = LucidMainWindowMenu(self)
        self.setMenuBar(self.menu)
        self.menu.exit.triggered.connect(self.close)

        # Restore settings prior to setting up the toolbar/dock
        # TODO: look into why restoring geometry post-dock_manager
        # instantiation causes y-offset/shrinking height
        self._restore_settings()

        # Toolbar
        self.toolbar = LucidToolBar(self)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # Use the dockmanager for the main window - it will set itself as the
        # central widget
        self.dock_manager = QtAds.CDockManager(self)
        self.dock_manager.setStyleSheet(
            open(MODULE_PATH / 'dock_style.css', 'rt').read())

    @property
    def settings(self):
        'Dictionary of application-level settings'
        return dict(self.menu.settings)

    def closeEvent(self, ev):
        self._save_settings()

    def _restore_settings(self):
        app = QtWidgets.QApplication.instance()
        settings = QtCore.QSettings(app.organizationName(),
                                    app.applicationName())
        geometry = settings.value('geometry', QtCore.QByteArray())
        if not geometry.isEmpty():
            self.restoreGeometry(geometry)

        for key in settings.allKeys():
            value = settings.value(key, None)
            if key in self.settings and value is not None:
                setattr(self.menu, key, value)

    def _save_settings(self):
        app = QtWidgets.QApplication.instance()
        settings = QtCore.QSettings(app.organizationName(),
                                    app.applicationName())
        settings.setValue('geometry', self.saveGeometry())
        for key, value in self.settings.items():
            settings.setValue(key, value)

    def keyPressEvent(self, ev):
        'Keypress event callback from Qt'
        if ev.key() == Qt.Key_Escape:
            self.escape_pressed.emit()
        super().keyPressEvent(ev)

    @classmethod
    def find_window(cls, widget):
        """
        Navigate the widget hierarchy to find instance of LucidMainWindow

        Parameters
        ----------
        widget: QWidget

        Returns
        -------
        window: LucidMainWindow
        """
        parent = widget.parent()
        if isinstance(parent, cls):
            return parent
        elif parent is None:
            raise EnvironmentError("No LucidMainWindow can be found "
                                   "in widget hierarchy")
        return cls.find_window(parent)

    @classmethod
    def in_dock(cls, func=None, title=None, area=None, active_slot=None):
        """
        Wrapper to show QWidget in ``LucidMainWindow``

        This allows any widget that is contained within the ``LucidMainWindow``
        the ability to display a widget in the docking system without needing
        to have direct access to the ``LucidMainWindow`` itself.

        The widget returned **must** share a parent hierarchy with a
        ``LucidMainWindow``. See :meth:`.find_window` for more detail.

        Parameters
        ----------
        cls: ``LucidMainWindow``

        func: callable
            Method which returns a QWidget whose parentage can be traced back
            to a ``LucidMainWindow`` instance

        title: str, optional
            Title for QDockWidget. This is what will be displayed in the tab
            system

        area: ``QDockWidgetArea``, optional
            If None, this wil be the first area in
            ``LucidMainWindow.allowed_docks``

        active_slot: callable, optional
            Callable which accepts a boolean argument. This will be called when
            the widget is closed or opened. This does not include when the
            QDockWidget is hidden behind another tab in the docking system.
            This will only be connected the first time a widget is added to the
            docking system

        Example
        -------
        .. code:: python

            @LucidMainWindow.in_dock(title='My Button')
            def dock_my_button(parent):
                button = QPushButton(parent=parent)
                return button

        """
        # When the decorator is not called
        if not func:
            return functools.partial(cls.in_dock, area=area, title=title,
                                     active_slot=active_slot)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal title

            # Retrieve widget
            widget = func()
            window = LucidMainWindow()

            # Add the widget to the dock
            if not title:
                title = (widget.objectName() or
                         (widget.__class__.__name__ + hex(id(widget))[:5])
                         )

            dock = window.dock_manager.findDockWidget(title)
            if dock:
                if dock.isFloating():
                    window.dock_manager.addDockWidgetTab(
                        QtAds.RightDockWidgetArea, dock)
                dock.toggleView(True)
                return widget

            dock = QtAds.CDockWidget(title)
            dock.setWidget(widget)
            widget.setParent(dock)
            window.dock_manager.addDockWidgetTab(
                QtAds.RightDockWidgetArea, dock)

            # Ensure the main dock is actually visible
            widget.raise_()
            widget.setVisible(True)

            if active_slot:
                dock.viewToggled.connect(active_slot)
                active_slot(True)

            return widget

        return wrapper


class _SearchThread(QtCore.QThread):
    def __init__(self, func, callback, *, parent, kwargs):
        super().__init__(parent)
        self.func = func
        self.callback = callback
        self.kwargs = kwargs
        self.setTerminationEnabled(True)
        self.start()

    def run(self):
        try:
            self.func(self.callback, **self.kwargs)
        except Exception:
            logger.exception('Search thread failed! func=%s',
                             self.func.__name__)

SEARCH_PATTERN = re.compile(
    r'((?P<category>[a-z_][a-z0-9_]*):\s*)?(?P<text>[^ ]+)',
    re.VERBOSE | re.IGNORECASE
)

def split_search_pattern(text):
    '''
    Split search pattern into (optional) categories
    Patterns are space-delimited, with each entry as follows:
        category_name: text_to_match_in_category
        text_to_match_generally
    '''

    matches = list(m.groupdict()
                   for m in SEARCH_PATTERN.finditer(text.strip())
                   )
    by_category = [
        (m['category'], m['text'])
        for m in matches if m['category'] is not None
    ]

    general = [
        m['text']
        for m in matches if m['category'] is None
    ]

    if general:
        general.append(' '.join(general))

    return by_category, general


_HAPPI_CACHE = None


def _cell_match(cell, text_list, threshold=50):
    ratio = [(fuzzy_match(name, text, threshold=threshold), name)
             for name in cell.matchable_names
             for text in text_list
             ]
    if ratio:
        ratio.sort()
        return ratio[-1]

    return 0.0, ''


def _thread_grid_search(callback, *, general_search, category_search,
                        threshold):
    if not general_search:
        return

    main = LucidMainWindow.get_instance()
    for grid in main.findChildren(lucid.overview.IndicatorGrid):
        updated = False
        min_ratio = 0.0
        for group_name, group in grid.groups.items():
            for cell in group.cells:
                ratio, match = _cell_match(cell, general_search,
                                           threshold=threshold)
                if ratio > threshold:
                    callback(dict(source='cell',
                                  rank=ratio,
                                  name=cell.title,
                                  item=cell,
                                  match_reason=match,
                                  callback=cell.click,
                                  )
                             )


def _thread_screens_search(callback, *, general_search, category_search,
                           threshold):
    if not general_search:
        return

    main = LucidMainWindow.get_instance()
    for display in main.findChildren(typhon.TyphonDeviceDisplay):
        ratio = max(fuzzy_match(display.device_name, text, threshold=threshold)
                    for text in general_search)
        if ratio > threshold:
            callback(dict(source='screens',
                          rank=ratio,
                          name=display.device_name,
                          item=display,
                          match_reason='',
                          callback=display.raise_,
                          )
                     )


def _thread_happi_search(callback, *, general_search, category_search,
                         threshold):
    '''
    Search happi
    '''
    global _HAPPI_CACHE
    if _HAPPI_CACHE is None:
        # TODO: re-read happi after a certain interval?
        client = get_happi_client()
        _HAPPI_CACHE = list(client.search(as_dict=True))

    for item in _HAPPI_CACHE:
        item_results = []
        for key, text in category_search:
            value = item.get(key)
            if value is not None:
                ratio = fuzzy_match(text, str(value), threshold=threshold)
                item_results.append((ratio, f'{key}: {value}'))

        for text in general_search:
            for key in ['name', 'prefix', 'stand']:
                value = item.get(key)
                if value is not None:
                    ratio = fuzzy_match(text, str(value), threshold=threshold)
                    item_results.append((ratio, f'{key}: {value}'))

        if item_results:
            item_results.sort(reverse=True)
            ratio, match = item_results[0]
            if ratio > threshold:
                callback(dict(source='happi',
                              rank=ratio,
                              name=item['name'],
                              item=item,
                              match_reason=match,
                              callback=None,  # TODO: find or create display
                              )
                         )


def _stringify_dict(d, skip_keys, prefix=' -', delim='\n'):
    return '\n'.join(f'{prefix}{key}: {value}'
                     for key, value in d.items()
                     if key not in skip_keys)


class SearchModelItem(QtGui.QStandardItem):
    def __init__(self, *, name, rank, item, match_reason, **info):
        '''
        A single item shown in the search results.

        Parameters
        ----------
        name : str
            The cell/device/etc. name
        rank : int
            Sort rank, 0-100 where 100 is the best match
        item : object
            The object related to the item
        match_reason : str
            The reason for the match
        **info : dict
            Additional information. Recognized keys include::
                {'callback', }
        '''
        self.info = info
        self.item = item
        self.name = name
        self.match_reason = match_reason

        if len(match_reason) > 40:
            match_reason = match_reason[:40] + '...'
        text = f'{name} ({match_reason})' if match_reason else name

        super().__init__(text)

        tooltip = '\n'.join((match_reason,
                             '------------',
                             str(_stringify_dict(item, skip_keys=())
                                 if isinstance(item, dict) else item),
                             '',
                             _stringify_dict(info, skip_keys=('item', )),
                             ))

        self.rank = rank
        self.setData(self.rank, Qt.UserRole)
        self.setData(tooltip, Qt.ToolTipRole)
        self.setEditable(False)

    def run_callback(self):
        callback = self.info.get('callback')
        if callback is None:
            logger.debug('No callback for %s', self)
            return

        try:
            callback()
        except Exception:
            logger.exception('Error while running callback for %s (%r)',
                             self, self.data())


class SearchModel(QtGui.QStandardItemModel):
    new_result = Signal(dict)

    def __init__(self, text, *, search_happi=True, search_grid=True,
                 search_screens=True, threshold=60):
        super().__init__(0, 1)

        category_search, general_search = split_search_pattern(text)
        self.new_result.connect(self.add_result)

        self.search_threads = [
            _SearchThread(func, self.new_result.emit, parent=self,
                          kwargs=dict(category_search=category_search,
                                      general_search=general_search,
                                      threshold=threshold,))
            for category, func, enabled
            in [('happi', _thread_happi_search, search_happi),
                ('grid', _thread_grid_search, search_grid),
                ('screens', _thread_screens_search, search_screens)]
            if enabled
        ]

    def add_result(self, info):
        self.appendRow(SearchModelItem(**info))

    def cancel(self):
        ...


class SearchDialog(QtWidgets.QDialog):
    def __init__(self, *, main_window, parent=None):
        super().__init__(parent=parent)

        self.main = main_window
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.Popup, True)

        if hasattr(parent, 'key_pressed'):
            parent.key_pressed.connect(self._handle_search_keypress)

        # [match list]
        # [option frame]
        layout = QtWidgets.QVBoxLayout()
        self.match_list = SearchMatchList()
        self.models = {}  # TODO: FIFO bounded dict

        self.setLayout(layout)
        layout.addWidget(self.match_list)

        self.proxy_model = QtCore.QSortFilterProxyModel()
        self.proxy_model.setSortRole(Qt.UserRole)
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.sort(0, Qt.DescendingOrder)
        self.match_list.setModel(self.proxy_model)

        # option frame:
        # [ grid screens happi ]
        option_frame = QtWidgets.QFrame()
        option_frame.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(option_frame)

        option_layout = QtWidgets.QHBoxLayout()
        option_frame.setLayout(option_layout)

        self.option_grid = QtWidgets.QCheckBox('&Grid')
        self.option_screens = QtWidgets.QCheckBox('&Screens')
        self.option_happi = QtWidgets.QCheckBox('&Happi')

        for w in (self.option_grid, self.option_screens, self.option_happi):
            option_layout.addWidget(w)
            w.setChecked(True)
            w.stateChanged.connect(lambda state: self._search_settings_changed())

    @property
    def text(self):
        return self.parent().text()

    def _search_settings_changed(self):
        self.search(self.text)

    def search(self, text):
        key = (text, self.option_happi.isChecked(),
               self.option_grid.isChecked(), self.option_screens.isChecked())
        try:
            model = self.models[key]
        except KeyError:
            model = SearchModel(text,
                                search_happi=self.option_happi.isChecked(),
                                search_grid=self.option_grid.isChecked(),
                                search_screens=self.option_screens.isChecked()
                                )
            self.models[key] = model

        self.proxy_model.setSourceModel(model)

    def _handle_search_keypress(self, event):
        key = event.key()
        if key in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp,
                   Qt.Key_Return):
            app = QtWidgets.QApplication.instance()
            app.sendEvent(self.match_list, event)

    def cancel(self):
        ...


class SearchMatchList(QtWidgets.QListView):
    def doubleClicked(self, index : QtCore.QModelIndex):
        proxy_model = self.model()
        model = proxy_model.sourceModel()
        item = model.itemFromIndex(proxy_model.mapToSource(index))
        item.run_callback()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            try:
                index, = self.selectedIndexes()
            except Exception:
                ...
            else:
                self.doubleClicked(index)
                return

        super().keyPressEvent(event)


class SearchLineEdit(QtWidgets.QLineEdit):
    key_pressed = Signal(QtGui.QKeyEvent)

    def __init__(self, *, main_window, parent=None):
        super().__init__(parent=parent)

        self.main = main_window
        self.search_frame = None
        self.setPlaceholderText("Search...")
        self.setClearButtonEnabled(True)

        def text_changed(text):
            self.show_search()

        self.textChanged.connect(text_changed)
        self.textChanged.connect(self.highlight_matches)

        def clear_highlight():
            if self.hasFocus():
                self.setText('')
            self.clear_highlight()

        self.main.escape_pressed.connect(clear_highlight)

    def keyPressEvent(self, ev):
        'Keypress event callback from Qt'
        self.key_pressed.emit(ev)
        super().keyPressEvent(ev)

    def show_search(self):
        corner_pos = self.mapToGlobal(self.rect().bottomLeft())

        if self.search_frame is None:
            self.search_frame = SearchDialog(parent=self,
                                             main_window=self.main)

            width = 20 * self.height()
            height = 10 * self.height()
            self.search_frame.setGeometry(
                corner_pos.x(), corner_pos.y(),
                width, height)
        else:
            self.search_frame.setGeometry(
                corner_pos.x(), corner_pos.y(),
                self.search_frame.width(),
                self.search_frame.height())

        self.search_frame.search(self.text().strip())
        self.search_frame.setVisible(True)
        self.search_frame.raise_()

    @property
    def overlay_visible(self):
        'Are any overlays visible?'
        return any(
            grid.overlay.visible()
            for grid in self.main.findChildren(lucid.overview.IndicatorGrid)
        )

    def highlight_matches(self, text):
        'Highlight cell matches given `text`'
        text = text.strip()
        if not self.main.settings['search_overlay']:
            self.clear_highlight()
            return

        if not text:
            self.clear_highlight()
            return

        _, general_search = split_search_pattern(text)

        for grid in self.main.findChildren(lucid.overview.IndicatorGrid):
            updated = False
            min_ratio = 0.0
            for group_name, group in grid.groups.items():
                for cell in group.cells:
                    old_ratio = grid.overlay.cell_to_percentage.get(cell, 0.0)
                    new_ratio, matched = _cell_match(cell, general_search)
                    new_ratio /= 100.
                    if old_ratio != new_ratio:
                        grid.overlay.cell_to_percentage[cell] = new_ratio
                        updated = True

                    min_ratio = max((min_ratio, new_ratio))

            grid.overlay.setVisible(True)

            if updated:
                grid.overlay.repaint()

    def clear_highlight(self):
        'Hide the highlighting overlay'
        for grid in self.main.findChildren(lucid.overview.IndicatorGrid):
            grid.overlay.setVisible(False)

        if self.search_frame is not None:
            self.search_frame.cancel()
            self.search_frame.setVisible(False)


class LucidToolBar(QToolBar):
    """LucidToolBar for LucidMainWindow"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Toolbar Configuration
        self.setMovable(False)
        self.setLayoutDirection(Qt.LeftToRight)
        # Back and Forward
        self.addAction(self.style().standardIcon(QStyle.SP_ArrowLeft),
                       'Back')
        self.addAction(self.style().standardIcon(QStyle.SP_ArrowRight),
                       'Forward')
        self.addSeparator()
        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.MinimumExpanding,
                             QSizePolicy.MinimumExpanding)
        self.addWidget(spacer)
        # Search
        self.search_edit = SearchLineEdit(main_window=self.parent())
        self.addWidget(self.search_edit)
