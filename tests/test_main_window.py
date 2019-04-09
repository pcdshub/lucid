import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDockWidget, QWidget

from lucid import LucidMainWindow


@pytest.fixture(scope='function')
def main_window(qtbot):
    main_window = LucidMainWindow()
    qtbot.addWidget(main_window)
    return main_window


def test_main_window_find_window(main_window, qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    dock = QDockWidget()
    qtbot.addWidget(dock)
    dock.setWidget(widget)
    main_window.addDockWidget(Qt.RightDockWidgetArea, dock)
    assert LucidMainWindow.find_window(widget) == main_window


def test_main_window_find_window_with_orphan(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    with pytest.raises(EnvironmentError):
        LucidMainWindow.find_window(widget)


def test_main_window_setup_dock(main_window):
    dock = main_window.setup_dock()
    assert main_window.dock_manager is not None


def test_main_window_repeat_setup_dock(main_window):
    dock = main_window.setup_dock()
    assert id(dock) == id(main_window.setup_dock())


def test_main_window_reopen_dock(main_window):
    dock = main_window.setup_dock()
    dock.close()
    assert main_window.dock_manager is None
    dock = main_window.setup_dock()
    assert main_window.dock_manager is not None


def test_main_window_in_dock(main_window, qtbot):
    widget_name = 'my_dock'
    title = 'Test Dock'

    @LucidMainWindow.in_dock(area=Qt.RightDockWidgetArea,
                             title=title)
    def create_widget():
        widget = QWidget(parent=main_window)
        widget.setObjectName(widget_name)
        qtbot.addWidget(widget)
        return widget

    widget = create_widget()

    assert main_window.dock_manager is not None
    dock = main_window.dock_manager.find_dock_widget(widget_name)
    assert dock is not None
    assert dock.widget() == widget


def test_main_window_in_dock_with_orphan(qtbot):

    @LucidMainWindow.in_dock
    def create_widget():
        widget = QWidget()
        qtbot.addWidget(widget)
        return widget

    widget = create_widget()
    assert widget.isVisible()
