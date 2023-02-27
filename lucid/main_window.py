import functools
import logging

import typhos
from pydm import exception
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QMainWindow, QSizePolicy, QStyle

import lucid

from . import utils
from .dock import DockManager, DockWidget

logger = logging.getLogger(__name__)

_ICONS = {}


class LucidMainWindowMenu(QtWidgets.QMenuBar):
    settings_changed = Signal(dict)
    exit_request = Signal()
    search_overlay_changed = Signal(bool)

    def __init__(self, parent, *, settings=None):
        super().__init__(parent)
        self.main = parent
        self.settings = dict(settings or {})
        self.actions = {}
        self._create_menu()

    def _create_menu(self):
        # File
        self.file_menu = self.addMenu('&File')
        # - Exit
        self.exit = self.file_menu.addAction('E&xit')

        # Tools
        self.tools_menu = self.addMenu('&Tools')
        # - Gather windows
        self.gather_windows = self.tools_menu.addAction('&Gather windows...')

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
                    if isinstance(value, str):
                        value = value == "true"
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
    dark: bool
        Whether or not to use the dark stylesheet
    """
    __instance = None
    escape_pressed = Signal()
    window_moved = Signal(QtGui.QMoveEvent)
    dock_manager: DockManager

    def __init__(self, parent=None, dark=False):
        if self.__initialized:
            return
        self.dock_manager = None
        self.dark = dark
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

    def moveEvent(self, event):
        self.window_moved.emit(event)
        super().moveEvent(event)

    def setup_ui(self):
        # Menu
        self.menu = LucidMainWindowMenu(self)
        self.setMenuBar(self.menu)
        self.menu.exit.triggered.connect(self.close)
        self.menu.gather_windows.triggered.connect(self.gather_windows)

        # Restore settings prior to setting up the toolbar/dock
        # TODO: look into why restoring geometry post-dock_manager
        # instantiation causes y-offset/shrinking height
        self._restore_settings()

        # Toolbar
        self.toolbar = LucidToolBar(self)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # Use the dockmanager for the main window - it will set itself as the
        # central widget
        self.dock_manager = DockManager(self, dark=self.dark)

    def gather_windows(self):
        'Move all dock widgets to the right dock widget area'
        self.dock_manager.gather()

    @QtCore.Slot(tuple)
    def handle_error(self, exc_info):
        exc_type, exc_value, exc_trace = exc_info
        logger.exception("An uncaught exception happened: %s", exc_value,
                         exc_info=exc_info)

        utils.log_exception_to_central_server(exc_info)
        exception.raise_to_operator(exc_value)

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
            raise OSError("No LucidMainWindow can be found in widget hierarchy")
        return cls.find_window(parent)

    def find_dock_widget_by_title(self, title):
        '''
        Find a dock widget given its title

        Parameters
        ----------
        title : str
            The title to find

        Returns
        -------
        dock_widget : QtAds.DockWidget or None
        '''
        return self.dock_manager.find_dock_widget_by_title(title)

    def add_dock(self, title, widget, *, area="right"):
        '''
        Add dock widget by title

        If the dock already exists, it will be re-docked if necessary.
        Otherwise, a new dock will be added to the given area.

        Parameters
        ----------
        title : str
            The DockWidget title
        widget : QWidget
            The widget to put inside the dock
        area : str, optional
            The area to put the dock in
        '''
        dock = self.dock_manager.redock(area, title)
        if dock is not None:
            return dock

        # The current minimumSizeHint from the widget is too small ~(68, 68)
        # Here we suggest the minimumSizeHint as being the size
        def min_size_hint(*args, **kwargs):
            return widget.sizeHint()

        widget.minimumSizeHint = min_size_hint
        widget.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored,
            QtWidgets.QSizePolicy.Ignored
        )

        dock = DockWidget(title)
        dock.set_widget(widget)
        self.dock_manager.add_dock_widget(area, dock)

        # Ensure the main dock is actually visible
        widget.raise_()
        widget.setVisible(True)
        return dock

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
            # Retrieve widget
            widget = func()
            if not widget:
                return
            dock_title = (title or
                          widget.objectName() or
                          (widget.__class__.__name__ + hex(id(widget))[:5])
                          )

            dock = LucidMainWindow().add_dock(title=dock_title, widget=widget, area="right")

            if active_slot:
                if hasattr(dock, "viewToggled"):
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


def _cell_match(cell, text_list, threshold=50):
    ratio = [(utils.fuzzy_match(name, text, threshold=threshold), name)
             for name in cell.matchable_names
             for text in text_list
             ]
    if ratio:
        ratio.sort()
        return ratio[-1]

    return 0.0, ''


def _thread_grid_search(callback, *, general_search, category_search,
                        threshold):
    'Search the main grid for the given text, running callback on each result'
    if not general_search:
        return

    main = LucidMainWindow.get_instance()
    for grid in main.findChildren(lucid.overview.IndicatorGrid):
        for group_name, group in grid.groups.items():
            if group.orientation == 'row':
                # Only iterate over vertical-column groups
                continue
            for cell in group.cells:
                if len(cell.devices) == 0:
                    continue
                ratio, match = _cell_match(cell, general_search,
                                           threshold=threshold)
                if ratio > threshold:
                    callback(
                        source='grid',
                        rank=ratio,
                        name=cell.title,
                        item=cell,
                        reason=match,
                        callback=cell.click,
                    )


def _raise_display(display):
    logger.debug('Bringing %s to the front', display)
    display.raise_()
    display.activateWindow()


def _thread_screens_search(callback, *, general_search, category_search,
                           threshold):
    'Search open screens for the given text, running callback on each result'
    if not general_search:
        return

    main = LucidMainWindow.get_instance()
    for display in main.findChildren(typhos.TyphosDeviceDisplay):
        ratio = max(utils.fuzzy_match(display.device_name, text,
                                      threshold=threshold)
                    for text in general_search)
        if ratio > threshold:
            callback(
                source='screens',
                rank=ratio,
                name=display.device_name,
                item=display,
                reason='device',
                callback=lambda disp=display: _raise_display(disp),
            )

    for suite in main.findChildren(typhos.TyphosSuite):
        suite_parent = suite.parent()
        if not hasattr(suite_parent, 'title'):
            continue

        ratio = max(utils.fuzzy_match(suite_parent.title, text,
                                      threshold=threshold)
                    for text in general_search)
        if ratio > threshold:
            callback(
                source='screens',
                rank=ratio,
                name=suite_parent.title,
                item=suite,
                reason='suite',
                callback=lambda disp=suite: _raise_display(disp),
            )


def _happi_searchresult_to_display(search_result):
    name = search_result['name']

    @LucidMainWindow.in_dock(title=f'[happi] {name}')
    def wrapped():
        device = search_result.get()
        return utils.display_for_device(device)

    wrapped()


def _thread_happi_search(callback, *, general_search, category_search,
                         threshold):
    'Search happi for the given text, running callback on each result'
    for item in utils.get_happi_device_cache():
        item_results = []
        for key, text in category_search:
            value = item.metadata.get(key)
            if value is not None:
                ratio = utils.fuzzy_match(text, str(value),
                                          threshold=threshold)
                item_results.append((ratio, key, value))

        for text in general_search:
            for key in utils.HAPPI_GENERAL_SEARCH_KEYS:
                value = item.metadata.get(key)
                if value is not None:
                    ratio = utils.fuzzy_match(text, str(value),
                                              threshold=threshold)
                    item_results.append((ratio, key, value))

        if not item_results:
            continue

        item_results.sort(reverse=True)
        ratio, key, value = item_results[0]
        if ratio > threshold:
            callback(
                source='happi',
                rank=ratio,
                name=item['name'],
                item=item,
                reason=f'{key}: {value}',
                callback=lambda ct=item: _happi_searchresult_to_display(ct),
            )


def _stringify_dict(d, skip_keys, prefix=' -', delim='\n'):
    return '\n'.join(f'{prefix}{key}: {value}'
                     for key, value in d.items()
                     if key not in skip_keys)


def _generate_icon(key):
    'Generate a simple icon based on the first letter of the `source` key'
    size = 128
    main = LucidMainWindow.get_instance()
    dpr = main.devicePixelRatioF()

    pixmap = QtGui.QPixmap(size * dpr, size * dpr)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)

    painter = QtGui.QPainter()
    painter.begin(pixmap)
    painter.setRenderHint(painter.Antialiasing)

    rect = QtCore.QRect(0, 0, size - 1, size - 1)

    font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.TitleFont)
    font.setPixelSize(size)
    font.setBold(True)
    painter.setFont(font)

    painter.drawEllipse(rect)
    painter.setPen(Qt.darkBlue)
    painter.drawText(rect, Qt.AlignCenter, key[0].upper())
    painter.end()
    return QtGui.QIcon(pixmap)


def get_search_icon_by_source(source):
    'Search result source -> QIcon'
    if source not in _ICONS:
        _ICONS[source] = _generate_icon(source)
    return _ICONS[source]


class SearchModelItem(QtGui.QStandardItem):
    def __init__(self, *, name, rank, item, reason, **info):
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
        reason : str
            The reason for the match
        **info : dict
            Additional information. Recognized keys include::
                {'callback', }
        '''
        self.info = info
        self.item = item
        self.name = name
        self.reason = reason

        if len(reason) > 40:
            reason = reason[:40] + '...'
        text = f'{name} ({reason})' if reason else name

        super().__init__(text)

        tooltip = '\n'.join(
            (reason,
             '------------',
             str(_stringify_dict(item, skip_keys=())
                 if isinstance(item, dict) else item),
             '',
             _stringify_dict(info, skip_keys=('item', 'callback')),
             )
        )

        self.rank = rank
        self.setIcon(get_search_icon_by_source(info['source']))
        self.setData(self.rank, Qt.UserRole)
        self.setData(tooltip, Qt.ToolTipRole)
        self.setEditable(False)

    def run_callback(self):
        callback = self.info.get('callback')
        if callback is None:
            logger.debug('No callback for %s', self)
            return

        callback()


class SearchModel(QtGui.QStandardItemModel):
    new_result = Signal(dict)

    def __init__(self, text, *, search_happi=True, search_grid=True,
                 search_screens=True, threshold=60):
        super().__init__(0, 1)

        category_search, general_search = utils.split_search_pattern(text)
        self.new_result.connect(self.add_result)

        def new_result(**kw):
            self.new_result.emit(kw)

        self._callback_results = set()
        self.search_threads = [
            _SearchThread(func, new_result, parent=self,
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
        key = (info['name'], info['source'], info['reason'])
        if key in self._callback_results:
            return
        self._callback_results.add(key)

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
        # Using SplashScreen and WindowDoesNotAcceptFocus to address issue when
        # running with OSX and XForwarding. Without the flag below it will make
        # the Dialog show its Title bar and appear over the search box which
        # makes the search useless.
        self.setWindowFlag(Qt.SplashScreen, True)
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)

        # Using BypassWindowManagerHint to address issue when running with
        # linux. Without the flag below it will make the Dialog capture the
        # focus from the line edit and clear the search result display along
        # with the overlay.
        self.setWindowFlag(Qt.BypassWindowManagerHint, True)

        if hasattr(parent, 'key_pressed'):
            parent.key_pressed.connect(self._handle_search_keypress)

        # [match list]
        # [option frame]
        layout = QtWidgets.QVBoxLayout()
        self.match_list = SearchMatchList(self)
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
        self.refresh_button = QtWidgets.QPushButton('&Refresh')

        for w in (self.option_grid, self.option_screens, self.option_happi):
            option_layout.addWidget(w)
            w.setChecked(True)
            w.stateChanged.connect(
                lambda state: self._search_settings_changed()
            )

        option_layout.addWidget(self.refresh_button)

        def refresh_clicked():
            self.search(self.text, force_update=True)

        self.refresh_button.clicked.connect(refresh_clicked)

    @property
    def text(self):
        'The search text from the parent (SearchLineEdit)'
        return self.parent().text()

    def _search_settings_changed(self):
        'Grid/screens/happi/etc parameters changed -> search again'
        self.search(self.text)

    def search(self, text, *, force_update=False):
        'Spawn a search for the given text, optionally clearing cached results'
        key = (text, self.option_happi.isChecked(),
               self.option_grid.isChecked(), self.option_screens.isChecked())

        if key not in self.models or force_update:
            model = SearchModel(text,
                                search_happi=self.option_happi.isChecked(),
                                search_grid=self.option_grid.isChecked(),
                                search_screens=self.option_screens.isChecked()
                                )
            self.models[key] = model

        self.proxy_model.setSourceModel(self.models[key])

    def _handle_search_keypress(self, event):
        'Forward SearchLineEdit keypresses to the match list'
        key = event.key()
        if key in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp,
                   Qt.Key_Return):
            app = QtWidgets.QApplication.instance()
            app.sendEvent(self.match_list, event)

    def cancel(self):
        ...


class SearchMatchList(QtWidgets.QListView):
    def __init__(self, parent):
        super().__init__(parent)
        self.doubleClicked.connect(self._run_callback)

    def _run_callback(self, index: QtCore.QModelIndex):
        proxy_model = self.model()
        model = proxy_model.sourceModel()
        item = model.itemFromIndex(proxy_model.mapToSource(index))
        try:
            item.run_callback()
        except Exception:
            logger.exception('Error while running callback for %s (%r)',
                             item, item.data())
        else:
            line_edit = utils.find_ancestor_widget(self, SearchLineEdit)
            if line_edit:
                line_edit.clear_highlight()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            try:
                index, = self.selectedIndexes()
            except Exception:
                ...
            else:
                self._run_callback(index)
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
            # TODO: rate limit and/or show only after a short delay
            if len(text.strip()) > 1:
                self.show_search()

        self.textChanged.connect(text_changed)
        self.textChanged.connect(self.highlight_matches)

        def clear_highlight():
            if self.hasFocus():
                self.setText('')
            self.clear_highlight()

        self.main.escape_pressed.connect(clear_highlight)
        self.main.window_moved.connect(self._reposition_search_frame)

    def focusOutEvent(self, event):
        'Search box lost keyboard focus'
        if self.search_frame and self.search_frame.isVisible():
            if not any(widget.hasFocus() for widget in
                       self.search_frame.findChildren(QtWidgets.QWidget)):
                self.clear_highlight()

        super().focusOutEvent(event)

    def _reposition_search_frame(self, *, width=None, height=None):
        'Reposition search frame to bottom-left corner of this line edit'
        if not self.search_frame:
            return
        corner_pos = self.mapToGlobal(self.rect().bottomLeft())
        self.search_frame.setGeometry(
            corner_pos.x(), corner_pos.y() + 1,
            width or self.search_frame.width(),
            height or self.search_frame.height()
        )

    def moveEvent(self, ev):
        'Widget movement event callback from Qt'
        if self.search_frame and self.search_frame.isVisible():
            self._reposition_search_frame()
        super().moveEvent(ev)

    def keyPressEvent(self, ev):
        'Keypress event callback from Qt'
        self.key_pressed.emit(ev)
        super().keyPressEvent(ev)

    def show_search(self):
        if self.search_frame is None:
            self.search_frame = SearchDialog(parent=self,
                                             main_window=self.main)

        self._reposition_search_frame(
            width=max((20 * self.height(), self.width())),
            height=10 * self.height()
        )

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

        _, general_search = utils.split_search_pattern(text)

        for grid in self.main.findChildren(lucid.overview.IndicatorGrid):
            updated = False
            min_ratio = 0.0
            for group_name, group in grid.groups.items():
                if group.orientation == 'row':
                    # Only iterate over vertical-column groups
                    continue
                for cell in group.cells:
                    if len(cell.devices) == 0:
                        continue
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


class LucidToolBar(QtWidgets.QToolBar):
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
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QSizePolicy.MinimumExpanding,
                             QSizePolicy.MinimumExpanding)
        self.addWidget(spacer)
        # Search
        self.search_edit = SearchLineEdit(main_window=self.parent())
        self.addWidget(self.search_edit)
